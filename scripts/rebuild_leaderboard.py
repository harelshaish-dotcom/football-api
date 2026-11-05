"""Rebuild the Redis leaderboard from the goal events in MongoDB.

Run with: python -m scripts.rebuild_leaderboard
Use it to recover after Redis lost data or the board drifted.
"""

import asyncio
import sys

from app.core.cache import get_top_scorers, rebuild_leaderboard, redis_client


async def main() -> int:
    """Rebuild and print the new top 10. Returns a process exit code."""
    try:
        if not await rebuild_leaderboard():
            print("Rebuild failed, see the warning above", file=sys.stderr)
            return 1
        print("Leaderboard rebuilt. Top 10:")
        for row in await get_top_scorers(limit=10):
            print(f"  #{row['rank']}  player {row['player_id']}: {row['goals']} goals")
        return 0
    finally:
        await redis_client.aclose()  # close before the event loop shuts down


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
