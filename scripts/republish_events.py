"""Send match events that never reached Kafka (outbox: published=false).

Run with: python -m scripts.republish_events [--min-age-seconds 30]

POST /matches/{id}/events saves each event with published=false and flips it to true once
Kafka acks. Events still false were saved while Kafka was down or the publish failed;
this sends them now. Workers dedupe by event_id, so a resend is harmless.
Events from before the outbox existed have no `published` field and are left alone.
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta

from bson import ObjectId

from app.core.events import publish_match_event, start_producer, stop_producer
from app.db.mongo import events


async def main(min_age_seconds: int) -> int:
    """Republish every unpublished event older than `min_age_seconds`. Returns an exit code."""
    # Skip very fresh events: their request may still be publishing right now.
    cutoff = ObjectId.from_datetime(datetime.now(UTC) - timedelta(seconds=min_age_seconds))
    pending = await events.find({"published": False, "_id": {"$lt": cutoff}}).to_list(None)
    if not pending:
        print("Nothing to republish.")
        return 0

    await start_producer()
    try:
        sent = 0
        for doc in pending:
            if await publish_match_event(doc):
                sent += 1
        print(f"Republished {sent}/{len(pending)} event(s).")
        return 0 if sent == len(pending) else 1
    finally:
        await stop_producer()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min-age-seconds", type=int, default=30)
    sys.exit(asyncio.run(main(parser.parse_args().min_age_seconds)))
