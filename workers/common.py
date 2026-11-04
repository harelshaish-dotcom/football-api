"""Shared plumbing for the Kafka workers: de-duplication, retries and the dead-letter queue."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from aiokafka import AIOKafkaConsumer
from aiokafka.structs import ConsumerRecord

from app.core.cache import redis_client
from app.core.events import publish, start_producer, stop_producer

MATCH_EVENTS_TOPIC = "match-events"
DLQ_TOPIC = "match-events-dlq"
MAX_ATTEMPTS = 3

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Log INFO and above to the console, keeping aiokafka's own logs quiet."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("aiokafka").setLevel(logging.WARNING)


async def claim(group_id: str, event_id: str) -> bool:
    """SET NX dedup: returns True the first time this event_id is seen, False on replay."""
    key = f"processed:{group_id}:{event_id}"
    was_new = await redis_client.set(key, "1", nx=True, ex=86400)
    return bool(was_new)


async def _handle_with_retry(
    msg: ConsumerRecord, group_id: str, handle: Callable[[dict], Awaitable[None]]
) -> None:
    """Try `handle` up to MAX_ATTEMPTS times; send the message to the DLQ if all fail."""
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            await handle(msg.value)
            last_error = None
            break
        except Exception as e:
            last_error = e
            logger.exception(
                "attempt %d/%d failed for partition=%s offset=%s: %s",
                attempt,
                MAX_ATTEMPTS,
                msg.partition,
                msg.offset,
                e,
            )
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(0.2 * attempt)

    if last_error is not None:
        await publish(
            DLQ_TOPIC,
            key=msg.key.decode() if msg.key else None,
            value={
                "original": msg.value,
                "error": str(last_error),
                "group_id": group_id,
                "attempts": MAX_ATTEMPTS,
            },
        )
        logger.error(
            "poison message sent to %s after %d attempts: partition=%s offset=%s",
            DLQ_TOPIC,
            MAX_ATTEMPTS,
            msg.partition,
            msg.offset,
        )


async def run_consumer(
    consumer: AIOKafkaConsumer,
    group_id: str,
    handle: Callable[[dict], Awaitable[None]],
    on_message: Callable[[ConsumerRecord], None] | None = None,
) -> None:
    """Consume messages forever, committing each offset after it is handled or dead-lettered.

    The producer is needed to publish to the dead-letter queue.
    """
    await start_producer()
    await consumer.start()
    try:
        async for msg in consumer:
            if on_message is not None:
                on_message(msg)
            await _handle_with_retry(msg, group_id, handle)
            await consumer.commit()
    finally:
        await stop_producer()
        await consumer.stop()
