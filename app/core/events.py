"""Kafka producer and topic setup, shared by the API and the workers."""

import json
import logging
from typing import Any

from aiokafka import AIOKafkaProducer
from aiokafka.admin import AIOKafkaAdminClient, NewTopic

from app.core.config import KAFKA_BOOTSTRAP_SERVERS
from app.db.mongo import events

logger = logging.getLogger(__name__)

MATCH_EVENTS_TOPIC = "match-events"
DLQ_TOPIC = "match-events-dlq"
TOPIC_PARTITIONS = 3  # lets up to 3 consumers in one group share the work

# Version of the match-event message format. Bump it when a field is renamed/removed or its
# meaning changes; consumers dead-letter versions they don't know instead of misreading them.
SCHEMA_VERSION = 1

producer: AIOKafkaProducer | None = None


async def ensure_topics() -> None:
    """Create match-events and match-events-dlq with TOPIC_PARTITIONS partitions if missing.

    Without this, the first publish auto-creates a topic with the broker default
    (num.partitions=1). Existing topics are left alone (Kafka can't shrink partitions,
    and growing them would reshuffle which partition each match_id key goes to).
    """
    admin = AIOKafkaAdminClient(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    await admin.start()
    try:
        existing = set(await admin.list_topics())
        missing = [t for t in (MATCH_EVENTS_TOPIC, DLQ_TOPIC) if t not in existing]
        if missing:
            new_topics = [
                NewTopic(name, num_partitions=TOPIC_PARTITIONS, replication_factor=1)
                for name in missing
            ]
            await admin.create_topics(new_topics)
            logger.info("created Kafka topics %s with %d partitions", missing, TOPIC_PARTITIONS)
    finally:
        await admin.close()


async def start_producer() -> None:
    """Connect the module-level Kafka producer. Raises if Kafka is unreachable.

    `producer` is only set once start() succeeded, so a failed start leaves it None
    instead of a half-initialised producer.
    """
    global producer
    p = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v, default=str).encode(),
        key_serializer=lambda k: str(k).encode(),
    )
    try:
        await p.start()
    except Exception:
        await p.stop()  # release the sockets/tasks start() opened
        raise
    producer = p


async def stop_producer() -> None:
    """Flush and close the producer, if it was started."""
    global producer
    if producer is not None:
        await producer.stop()
        producer = None


async def send(topic: str, key: Any, value: dict) -> None:
    """Send `value` to `topic` and wait for Kafka to acknowledge it. Raises on failure.

    Use this when the caller must know whether the message really got to Kafka
    (the API's outbox flag, the workers' dead-letter queue).
    """
    if producer is None:
        raise RuntimeError("Kafka producer is not started")
    await producer.send_and_wait(topic, key=key, value=value)


async def publish_match_event(doc: dict) -> bool:
    """Send a stored match event to Kafka and flip its outbox flag (published=true) on success.

    `doc` is the Mongo document (with `_id`). Returns False, leaving published=false, if
    Kafka didn't ack; scripts/republish_events.py retries those later. The workers dedupe
    by event_id, so sending the same event twice is safe.
    """
    event_id = str(doc["_id"])
    message = {
        "schema_version": SCHEMA_VERSION,
        "event_id": event_id,
        "match_id": doc["match_id"],
        "type": doc["type"],
        "player_id": doc["player"]["id"],
        "minute": doc["minute"],
    }
    if not await publish(MATCH_EVENTS_TOPIC, key=str(doc["match_id"]), value=message):
        return False
    await events.update_one({"_id": doc["_id"]}, {"$set": {"published": True}})
    return True


async def publish(topic: str, key: Any, value: dict) -> bool:
    """Best-effort send: logs failures instead of raising. Returns True if Kafka acked."""
    try:
        await send(topic, key, value)
        return True
    except Exception as e:
        logger.error("publish to %s failed: %s", topic, e)
        return False
