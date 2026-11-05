"""Stats worker: keeps the live Redis leaderboard and league-table cache up to date.

Run with: python -m workers.stats
"""

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer

from app.core.cache import delete_cached, rebuild_leaderboard
from app.core.config import KAFKA_BOOTSTRAP_SERVERS
from app.db.postgres import SessionLocal
from app.models import Player
from workers.common import (
    MATCH_EVENTS_TOPIC,
    is_processed,
    mark_processed,
    run_consumer,
    setup_logging,
)

GROUP_ID = "stats"

logger = logging.getLogger(__name__)


def get_league_id(player_id: int) -> int | None:
    """League of the player's team, or None if the player doesn't exist."""
    db = SessionLocal()
    try:
        player = db.get(Player, player_id)
        if player is None:
            logger.warning("goal event for unknown player_id=%s", player_id)
            return None
        return player.team.league_id
    finally:
        db.close()


async def handle_goal(event: dict) -> None:
    """Add the goal to the leaderboard and invalidate the league table cache, once per event."""
    if await is_processed(GROUP_ID, event["event_id"]):
        logger.info("duplicate event_id=%s, skipping (already processed)", event["event_id"])
        return

    # Recompute from Mongo instead of +1: the API also rebuilds on goal changes,
    # so an increment here would double-count.
    if await rebuild_leaderboard():
        logger.info("[stats] leaderboard rebuilt after goal by player %s", event["player_id"])

    league_id = get_league_id(event["player_id"])
    if league_id is not None:
        await delete_cached(f"league_table:{league_id}")
        logger.info("[stats] invalidated league_table cache for league %s", league_id)

    await mark_processed(GROUP_ID, event["event_id"])  # only reached if nothing above raised


async def handle(event: dict) -> None:
    """Handle one match event; only goals affect stats."""
    if event.get("type") != "goal":
        return
    await handle_goal(event)


async def main() -> None:
    """Start consuming match events in the `stats` group."""
    consumer = AIOKafkaConsumer(
        MATCH_EVENTS_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=GROUP_ID,
        value_deserializer=lambda b: json.loads(b.decode()),
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await run_consumer(consumer, GROUP_ID, handle)


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())
