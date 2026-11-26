import asyncio, json, os
from aiokafka import AIOKafkaConsumer
from aiokafka.abc import ConsumerRebalanceListener
import logging

from database.postgres import SessionLocal
from models import Player, Team, User
from core.cache import r
from core.events import start_producer, stop_producer, publish

GROUP_ID = "notifications"
WORKER_ID = os.getpid()
MAX_ATTEMPTS = 3
DLQ_TOPIC = "match-events-dlq"


async def claim(event_id: str) -> bool:
    """SET NX dedup: returns True the first time this event_id is seen, False on replay."""
    key = f"processed:{GROUP_ID}:{event_id}"
    was_new = await r.set(key, "1", nx=True, ex=86400)
    return bool(was_new)


def notify_goal(event: dict):
    db = SessionLocal()
    try:
        player = db.get(Player, event["player_id"])
        if player is None:
            logging.warning("goal event for unknown player_id=%s", event["player_id"])
            return

        team = player.team
        followers = (
            db.query(User)
            .join(User.followed_teams)
            .filter(Team.id == team.id)
            .all()
        )
        for user in followers:
            print(f"[notify:{WORKER_ID}] {user.email}: goal for {team.name} (match {event['match_id']}, minute {event['minute']})")
    finally:
        db.close()


async def handle(event: dict):
    if event.get("type") != "goal":
        return
    if not await claim(event["event_id"]):
        logging.info("duplicate event_id=%s, skipping (already processed)", event["event_id"])
        return
    notify_goal(event)


class LogRebalances(ConsumerRebalanceListener):
    async def on_partitions_revoked(self, revoked):
        if revoked:
            print(f"[notifications:{WORKER_ID}] partitions revoked: {sorted(p.partition for p in revoked)}")

    async def on_partitions_assigned(self, assigned):
        print(f"[notifications:{WORKER_ID}] partitions assigned: {sorted(p.partition for p in assigned)}")


async def main():
    consumer = AIOKafkaConsumer(
        bootstrap_servers="localhost:9092",
        group_id=GROUP_ID,
        value_deserializer=lambda b: json.loads(b.decode()),
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    consumer.subscribe(topics=["match-events"], listener=LogRebalances())
    await start_producer()
    await consumer.start()
    try:
        async for msg in consumer:
            print(f"[notifications:{WORKER_ID}] partition={msg.partition} offset={msg.offset} event_id={msg.value.get('event_id')}")

            last_error = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    await handle(msg.value)
                    last_error = None
                    break
                except Exception as e:
                    last_error = e
                    logging.exception(
                        "attempt %d/%d failed for partition=%s offset=%s: %s",
                        attempt, MAX_ATTEMPTS, msg.partition, msg.offset, e,
                    )
                    if attempt < MAX_ATTEMPTS:
                        await asyncio.sleep(0.2 * attempt)

            if last_error is not None:
                await publish(DLQ_TOPIC, key=msg.key.decode() if msg.key else None, value={
                    "original": msg.value,
                    "error": str(last_error),
                    "group_id": GROUP_ID,
                    "attempts": MAX_ATTEMPTS,
                })
                logging.error(
                    "poison message sent to %s after %d attempts: partition=%s offset=%s",
                    DLQ_TOPIC, MAX_ATTEMPTS, msg.partition, msg.offset,
                )

            await consumer.commit()
    finally:
        await stop_producer()
        await consumer.stop()


if __name__ == "__main__":
    asyncio.run(main())
