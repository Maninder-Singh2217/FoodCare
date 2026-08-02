"""User profile persistence per spec §3A.

Persisted fields: default_location, hard_no_list, dessert_rotation_pool,
drink_rotation_pool, last_rotation_index per pool.
Session-only ("Exclude Today Only" checkboxes) are NOT persisted here -
they live in st.session_state and reset every visit, default OFF.
Writes only happen on explicit user action (save default location, edit
Hard NOs) - never on every interaction.
"""
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "profile.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    default_location TEXT NOT NULL,
    hard_no_list TEXT NOT NULL,
    dessert_rotation_pool TEXT NOT NULL,
    drink_rotation_pool TEXT NOT NULL,
    dessert_rotation_index INTEGER NOT NULL,
    drink_rotation_index INTEGER NOT NULL
);
"""

DEFAULT_HARD_NOS = ["Mushrooms", "Bell Peppers (Capsicum)", "Overly Oily Gravies"]
DEFAULT_DESSERT_POOL = [
    "Nutella Dark Chocolate Waffle",
    "Blueberry Cream Cheese Waffle",
    "Warm Fudgy Brownie",
    "Gulab Jamun",
    "Almond Cocoa Butter Waffle",
]
DEFAULT_DRINK_POOL = [
    "Masala Chai",
    "Hot Chocolate",
    "Warm Honey Lemon Water",
    "Peach Iced Tea",
]
DEFAULT_LOCATION = "Bandra West"
KNOWN_AREAS = ["Bandra West", "Powai", "Lower Parel", "Andheri"]


@dataclass
class Profile:
    default_location: str = DEFAULT_LOCATION
    hard_no_list: list[str] = field(default_factory=lambda: list(DEFAULT_HARD_NOS))
    dessert_rotation_pool: list[str] = field(default_factory=lambda: list(DEFAULT_DESSERT_POOL))
    drink_rotation_pool: list[str] = field(default_factory=lambda: list(DEFAULT_DRINK_POOL))
    dessert_rotation_index: int = 0
    drink_rotation_index: int = 0

    def next_dessert(self) -> str:
        item = self.dessert_rotation_pool[self.dessert_rotation_index % len(self.dessert_rotation_pool)]
        return item

    def next_drink(self) -> str:
        item = self.drink_rotation_pool[self.drink_rotation_index % len(self.drink_rotation_pool)]
        return item

    def advance_dessert(self) -> None:
        self.dessert_rotation_index = (self.dessert_rotation_index + 1) % len(self.dessert_rotation_pool)

    def advance_drink(self) -> None:
        self.drink_rotation_index = (self.drink_rotation_index + 1) % len(self.drink_rotation_pool)


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.row_factory = sqlite3.Row
    return conn


def load_profile(conn: sqlite3.Connection) -> Profile:
    row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    if row is None:
        profile = Profile()
        save_profile(conn, profile)
        return profile
    return Profile(
        default_location=row["default_location"],
        hard_no_list=json.loads(row["hard_no_list"]),
        dessert_rotation_pool=json.loads(row["dessert_rotation_pool"]),
        drink_rotation_pool=json.loads(row["drink_rotation_pool"]),
        dessert_rotation_index=row["dessert_rotation_index"],
        drink_rotation_index=row["drink_rotation_index"],
    )


def save_profile(conn: sqlite3.Connection, profile: Profile) -> None:
    """Explicit-write path (§3A): call only on user-triggered save actions."""
    conn.execute(
        """
        INSERT INTO profile (id, default_location, hard_no_list, dessert_rotation_pool,
                              drink_rotation_pool, dessert_rotation_index, drink_rotation_index)
        VALUES (1, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            default_location=excluded.default_location,
            hard_no_list=excluded.hard_no_list,
            dessert_rotation_pool=excluded.dessert_rotation_pool,
            drink_rotation_pool=excluded.drink_rotation_pool,
            dessert_rotation_index=excluded.dessert_rotation_index,
            drink_rotation_index=excluded.drink_rotation_index
        """,
        (
            profile.default_location,
            json.dumps(profile.hard_no_list),
            json.dumps(profile.dessert_rotation_pool),
            json.dumps(profile.drink_rotation_pool),
            profile.dessert_rotation_index,
            profile.drink_rotation_index,
        ),
    )
    conn.commit()
