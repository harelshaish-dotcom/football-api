"""Kafka producer shared by the API and the workers."""

import json
import logging
from typing import Any

from aiokafka import AIOKafkaProducer

from app.core.config import KAFKA_BOOTSTRAP_SERVERS

producer: AIOKafkaProducer | None = None


async def start_producer() -> None:
    """Connect the module-level Kafka producer."""
    global producer
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v, default=str).encode(),
        key_serializer=lambda k: str(k).encode(),
    )
    await producer.start()


async def stop_producer() -> None:
    """Flush and close the producer, if it was started."""
    if producer is not None:
        await producer.stop()


async def publish(topic: str, key: Any, value: dict) -> None:
    """Send `value` to `topic`. Failures are logged, never raised."""
    try:
        await producer.send_and_wait(topic, key=key, value=value)
    except Exception as e:
        logging.error("publish failed: %s", e)  # decide: swallow or 503?
