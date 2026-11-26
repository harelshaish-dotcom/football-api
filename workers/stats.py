import asyncio, json
from aiokafka import AIOKafkaConsumer
import logging

from database.postgres import SessionLocal
from models import Player
from core.cache import r, update_leaderboard, delete_cached
from core.events import start_producer, stop_producer, publish

GROUP_ID = "stats"
MAX_ATTEMPTS = 3
DLQ_TOPIC = "match-events-dlq"


async def claim(event_id: str) -> bool:
    """SET NX dedup: returns True the first time this event_id is seen, False on replay."""
    key = f"processed:{GROUP_ID}:{event_id}"
    was_new = await r.set(key, "1", nx=True, ex=86400)
    return bool(was_new)


def get_league_id(player_id: int) -> int | None:
    db = SessionLocal()
    try:
        player = db.get(Player, player_id)
        if player is None:
            logging.warning("goal event for unknown player_id=%s", player_id)
            return None
        return player.team.league_id
    finally:
        db.close()


async def handle_goal(event: dict):
    if not await claim(event["event_id"]):
        logging.info("duplicate event_id=%s, skipping (already processed)", event["event_id"])
        return

    new_score = await update_leaderboard(event["player_id"])
    print(f"[stats] leaderboard: player {event['player_id']} -> {new_score} goals")

    league_id = get_league_id(event["player_id"])
    if league_id is not None:
        await delete_cached(f"league_table:{league_id}")
        print(f"[stats] invalidated league_table cache for league {league_id}")


async def handle(event: dict):
    if event.get("type") != "goal":
        return
    await handle_goal(event)


async def main():
    consumer = AIOKafkaConsumer(
        "match-events",
        bootstrap_servers="localhost:9092",
        group_id=GROUP_ID,
        value_deserializer=lambda b: json.loads(b.decode()),
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await start_producer()
    await consumer.start()
    try:
        async for msg in consumer:
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
