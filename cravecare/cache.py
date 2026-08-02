"""Recommendation cache per spec §3.3.

Runtime reads only ever hit this cache - no live external calls in the
request path. Cache is populated out-of-band by scripts/seed_cache.py
(prod: manual "Refresh recommendations" trigger; test: direct seeding).
"""
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_CACHE_PATH = Path(__file__).resolve().parent.parent / "cache.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS recommendation_cache (
    restaurant_id TEXT NOT NULL,
    dish_id TEXT NOT NULL,
    area TEXT NOT NULL,
    restaurant_name TEXT NOT NULL,
    dish_name TEXT NOT NULL,
    cuisine TEXT NOT NULL,
    tags TEXT NOT NULL,
    prep_delivery_minutes INTEGER NOT NULL,
    swiggy_rating REAL NOT NULL,
    google_rating REAL NOT NULL,
    reddit_score REAL,
    reddit_mentions_used INTEGER NOT NULL,
    quality_score REAL NOT NULL,
    last_updated TEXT NOT NULL,
    PRIMARY KEY (restaurant_id, dish_id, area)
);
"""


@dataclass
class CachedItem:
    restaurant_id: str
    dish_id: str
    area: str
    restaurant_name: str
    dish_name: str
    cuisine: str
    tags: list[str]
    prep_delivery_minutes: int
    swiggy_rating: float
    google_rating: float
    reddit_score: float | None
    reddit_mentions_used: int
    quality_score: float
    last_updated: str


def get_connection(db_path: Path = DEFAULT_CACHE_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.row_factory = sqlite3.Row
    return conn


def upsert_item(conn: sqlite3.Connection, item: CachedItem) -> None:
    conn.execute(
        """
        INSERT INTO recommendation_cache
            (restaurant_id, dish_id, area, restaurant_name, dish_name, cuisine, tags,
             prep_delivery_minutes, swiggy_rating, google_rating, reddit_score,
             reddit_mentions_used, quality_score, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(restaurant_id, dish_id, area) DO UPDATE SET
            restaurant_name=excluded.restaurant_name,
            dish_name=excluded.dish_name,
            cuisine=excluded.cuisine,
            tags=excluded.tags,
            prep_delivery_minutes=excluded.prep_delivery_minutes,
            swiggy_rating=excluded.swiggy_rating,
            google_rating=excluded.google_rating,
            reddit_score=excluded.reddit_score,
            reddit_mentions_used=excluded.reddit_mentions_used,
            quality_score=excluded.quality_score,
            last_updated=excluded.last_updated
        """,
        (
            item.restaurant_id, item.dish_id, item.area, item.restaurant_name,
            item.dish_name, item.cuisine, json.dumps(item.tags), item.prep_delivery_minutes,
            item.swiggy_rating, item.google_rating, item.reddit_score,
            item.reddit_mentions_used, item.quality_score, item.last_updated,
        ),
    )
    conn.commit()


def read_all(conn: sqlite3.Connection, area: str | None = None) -> list[CachedItem]:
    """Runtime read path (§3.3): cache-only, no live calls."""
    if area:
        rows = conn.execute(
            "SELECT * FROM recommendation_cache WHERE area = ? ORDER BY quality_score DESC", (area,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM recommendation_cache ORDER BY quality_score DESC"
        ).fetchall()
    return [
        CachedItem(
            restaurant_id=r["restaurant_id"], dish_id=r["dish_id"], area=r["area"],
            restaurant_name=r["restaurant_name"], dish_name=r["dish_name"],
            cuisine=r["cuisine"], tags=json.loads(r["tags"]),
            prep_delivery_minutes=r["prep_delivery_minutes"],
            swiggy_rating=r["swiggy_rating"], google_rating=r["google_rating"],
            reddit_score=r["reddit_score"], reddit_mentions_used=r["reddit_mentions_used"],
            quality_score=r["quality_score"], last_updated=r["last_updated"],
        )
        for r in rows
    ]


def latest_updated_at(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT MAX(last_updated) AS m FROM recommendation_cache").fetchone()
    return row["m"] if row else None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
