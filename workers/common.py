"""Shared plumbing for the Kafka workers: de-duplication, retries and the dead-letter queue."""

import asyncio
import logging
import signal
from collections.abc import Awaitable, Callable

from aiokafka import AIOKafkaConsumer
from aiokafka.structs import ConsumerRecord, TopicPartition

from app.core.cache import redis_client
from app.core.events import (
    DLQ_TOPIC,
    MATCH_EVENTS_TOPIC,
    SCHEMA_VERSION,
    ensure_topics,
    send,
    start_producer,
    stop_producer,
)
from app.db.postgres import engine

__all__ = ["DLQ_TOPIC", "MATCH_EVENTS_TOPIC"]  # re-exported for the workers

MAX_ATTEMPTS = 3
BATCH_SIZE = 100  # max messages handled per commit
SUPPORTED_SCHEMA_VERSIONS = {SCHEMA_VERSION}

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Log INFO and above to the console, keeping aiokafka's and SQLAlchemy's logs quiet."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("aiokafka").setLevel(logging.WARNING)
    # The shared engine is created with echo=True for the API; in the workers every
    # query would be printed (twice), burying the worker's own log lines.
    engine.echo = False


def _processed_key(group_id: str, event_id: str) -> str:
    return f"processed:{group_id}:{event_id}"


async def is_processed(group_id: str, event_id: str) -> bool:
    """True if this group already finished handling this event_id (a replay/duplicate)."""
    return bool(await redis_client.exists(_processed_key(group_id, event_id)))


async def mark_processed(group_id: str, event_id: str) -> None:
    """Record that this group finished handling event_id. Call only AFTER the work succeeded.

    Marking after (not before) the work means a failure or a crash leaves no mark, so the
    retry / redelivery does the work again instead of skipping it as a "duplicate".
    Trade-off: a crash between the work and this call makes the work run twice
    (at-least-once), so handlers should tolerate an occasional repeat.
    """
    await redis_client.set(_processed_key(group_id, event_id), "1", ex=86400)


async def _dead_letter(msg: ConsumerRecord, group_id: str, error: str, attempts: int) -> None:
    """Send `msg` to the DLQ. Raises if Kafka doesn't ack (see run_consumer for why)."""
    await send(
        DLQ_TOPIC,
        key=msg.key.decode() if msg.key else None,
        value={
            "original": msg.value,
            "error": error,
            "group_id": group_id,
            "attempts": attempts,
        },
    )
    logger.error(
        "message sent to %s after %d attempt(s): partition=%s offset=%s error=%s",
        DLQ_TOPIC,
        attempts,
        msg.partition,
        msg.offset,
        error,
    )


async def _handle_with_retry(
    msg: ConsumerRecord, group_id: str, handle: Callable[[dict], Awaitable[None]]
) -> None:
    """Try `handle` up to MAX_ATTEMPTS times; send the message to the DLQ if all fail.

    A message with a schema_version this worker doesn't understand goes straight to the
    DLQ: retrying can't help, and guessing at an unknown format could do the wrong thing.
    """
    version = msg.value.get("schema_version", 1)  # messages from before versioning are v1
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        await _dead_letter(msg, group_id, f"unsupported schema_version {version!r}", attempts=0)
        return

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            await handle(msg.value)
            return
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

    # _dead_letter raises if Kafka doesn't ack. That exception must escape: run_consumer
    # then stops without committing this message, so it is redelivered on restart
    # instead of being committed while it exists nowhere (not handled, not in the DLQ).
    await _dead_letter(msg, group_id, str(last_error), attempts=MAX_ATTEMPTS)


def _install_stop_handler() -> asyncio.Event:
    """Ctrl+C / SIGTERM -> finish the current message, commit, then stop. Twice -> quit now.

    Uses signal.signal (loop.add_signal_handler isn't available on Windows).
    """
    loop = asyncio.get_running_loop()
    stopping = asyncio.Event()

    def on_signal(signum, frame) -> None:
        if stopping.is_set():
            raise KeyboardInterrupt  # second signal: stop immediately
        logger.info("shutdown requested: finishing the current message (again to force)")
        loop.call_soon_threadsafe(stopping.set)

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    return stopping


async def run_consumer(
    consumer: AIOKafkaConsumer,
    group_id: str,
    handle: Callable[[dict], Awaitable[None]],
    on_message: Callable[[ConsumerRecord], None] | None = None,
) -> None:
    """Consume until asked to stop, committing in batches (at most BATCH_SIZE messages).

    Each batch commits, per partition, the offset after the last message that was handled
    or dead-lettered, so one commit covers many messages instead of one round-trip each.

    If a message can be neither handled nor dead-lettered, the exception stops the worker:
    the messages before it in the batch are committed, it and everything after it are not,
    so Kafka redelivers them on restart. (Committing a later offset would silently commit
    past it.) Redelivered messages that were already handled are skipped by is_processed().
    """
    await ensure_topics()
    await start_producer()
    await consumer.start()
    stopping = _install_stop_handler()
    try:
        while not stopping.is_set():
            batch = await consumer.getmany(timeout_ms=1000, max_records=BATCH_SIZE)
            done: dict[TopicPartition, int] = {}  # partition -> next offset to commit
            try:
                for tp, messages in batch.items():
                    for msg in messages:
                        if stopping.is_set():
                            break  # unprocessed messages aren't committed -> redelivered
                        if on_message is not None:
                            on_message(msg)
                        await _handle_with_retry(msg, group_id, handle)
                        done[tp] = msg.offset + 1
            finally:
                if done:
                    await consumer.commit(done)
        logger.info("stopped cleanly")
    finally:
        await stop_producer()
        await consumer.stop()
