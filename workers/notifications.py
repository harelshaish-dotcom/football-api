"""Notifications worker: tells followers of a team when that team scores.

Run with: python -m workers.notifications
Start several copies to see Kafka spread partitions across one consumer group.
"""

import asyncio
import json
import logging
import os

from aiokafka import AIOKafkaConsumer
from aiokafka.abc import ConsumerRebalanceListener
from aiokafka.structs import ConsumerRecord

from app.core.config import KAFKA_BOOTSTRAP_SERVERS
from app.db.postgres import SessionLocal
from app.models import Player, Team, User
from workers.common import MATCH_EVENTS_TOPIC, claim, run_consumer, setup_logging

GROUP_ID = "notifications"
WORKER_ID = os.getpid()

logger = logging.getLogger(__name__)


def notify_goal(event: dict) -> None:
    """Notify every follower of the scoring player's team (currently: log a line each)."""
    db = SessionLocal()
    try:
        player = db.get(Player, event["player_id"])
        if player is None:
            logger.warning("goal event for unknown player_id=%s", event["player_id"])
            return

        team = player.team
        followers = db.query(User).join(User.followed_teams).filter(Team.id == team.id).all()
        for user in followers:
            logger.info(
                "[notify:%s] %s: goal for %s (match %s, minute %s)",
                WORKER_ID,
                user.email,
                team.name,
                event["match_id"],
                event["minute"],
            )
    finally:
        db.close()


async def handle(event: dict) -> None:
    """Handle one match event; only goals trigger notifications, each at most once."""
    if event.get("type") != "goal":
        return
    if not await claim(GROUP_ID, event["event_id"]):
        logger.info("duplicate event_id=%s, skipping (already processed)", event["event_id"])
        return
    notify_goal(event)


class LogRebalances(ConsumerRebalanceListener):
    """Log which partitions this worker gains or loses when the group rebalances."""

    async def on_partitions_revoked(self, revoked) -> None:
        if revoked:
            logger.info(
                "[notifications:%s] partitions revoked: %s",
                WORKER_ID,
                sorted(p.partition for p in revoked),
            )

    async def on_partitions_assigned(self, assigned) -> None:
        logger.info(
            "[notifications:%s] partitions assigned: %s",
            WORKER_ID,
            sorted(p.partition for p in assigned),
        )


def log_message(msg: ConsumerRecord) -> None:
    """Log where each message came from (shows partition ownership per worker)."""
    logger.info(
        "[notifications:%s] partition=%s offset=%s event_id=%s",
        WORKER_ID,
        msg.partition,
        msg.offset,
        msg.value.get("event_id"),
    )


async def main() -> None:
    """Start consuming match events in the `notifications` group."""
    consumer = AIOKafkaConsumer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=GROUP_ID,
        value_deserializer=lambda b: json.loads(b.decode()),
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    consumer.subscribe(topics=[MATCH_EVENTS_TOPIC], listener=LogRebalances())
    await run_consumer(consumer, GROUP_ID, handle, on_message=log_message)


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())
