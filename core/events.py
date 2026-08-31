import json
from aiokafka import AIOKafkaProducer

producer: AIOKafkaProducer | None = None


async def start_producer():
    global producer
    producer = AIOKafkaProducer(
        bootstrap_servers="localhost:9092",
        value_serializer=lambda v: json.dumps(v, default=str).encode(),
        key_serializer=lambda k: str(k).encode(),
    )
    await producer.start()


async def publish(topic: str, key, value: dict):
    try:
        await producer.send_and_wait(topic, key=key, value=value)
    except Exception as e:
        logging.error("publish failed: %s", e)   # decide: swallow or 503?