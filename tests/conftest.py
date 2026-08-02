import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cravecare import cache as cache_module
from cravecare import persistence as persistence_module
from scripts.seed_cache import seed

FIXTURES_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "raw_sources.json"


@pytest.fixture
def seeded_cache_conn(tmp_path):
    """Tier 3: seeded cache fixture, per §3.3's testing note (direct seed, no live calls)."""
    db_path = tmp_path / "cache.db"
    seed(db_path, FIXTURES_PATH)
    conn = cache_module.get_connection(db_path)
    yield conn
    conn.close()


@pytest.fixture
def fresh_profile_conn(tmp_path):
    db_path = tmp_path / "profile.db"
    conn = persistence_module.get_connection(db_path)
    yield conn
    conn.close()
