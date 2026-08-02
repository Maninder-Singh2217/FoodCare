"""Seeds the recommendation cache (§3.3) from fixtures/raw_sources.json.

Stands in for the production "manual Refresh recommendations" trigger.
Used directly (not via the trigger) for Tier 3 test fixtures per §3.3's
testing note. Run: python scripts/seed_cache.py [--db path] [--fixtures path]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cravecare import cache, scoring

DEFAULT_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "raw_sources.json"


def seed(db_path: Path = cache.DEFAULT_CACHE_PATH, fixtures_path: Path = DEFAULT_FIXTURES) -> int:
    data = json.loads(fixtures_path.read_text())
    conn = cache.get_connection(db_path)
    now = cache.now_iso()
    count = 0
    for c in data["candidates"]:
        breakdown = scoring.compute_quality_score(
            c["swiggy_rating"], c["google_rating"], c["reddit_comments"]
        )
        item = cache.CachedItem(
            restaurant_id=c["restaurant_id"],
            dish_id=c["dish_id"],
            area=c["area"],
            restaurant_name=c["restaurant_name"],
            dish_name=c["dish_name"],
            cuisine=c["cuisine"],
            tags=c.get("tags", []),
            prep_delivery_minutes=c["prep_delivery_minutes"],
            swiggy_rating=c["swiggy_rating"],
            google_rating=c["google_rating"],
            reddit_score=breakdown.reddit_score,
            reddit_mentions_used=breakdown.reddit_mentions_used,
            quality_score=breakdown.quality_score,
            last_updated=now,
        )
        cache.upsert_item(conn, item)
        count += 1
    conn.close()
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=cache.DEFAULT_CACHE_PATH)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    args = parser.parse_args()
    n = seed(args.db, args.fixtures)
    print(f"Seeded {n} items into {args.db}")
