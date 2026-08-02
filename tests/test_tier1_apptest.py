"""Tier 1: AppTest state/selection-flow tests (§4), run against app.py.

Written against fixture data (seeded via CRAVECARE_CACHE_DB/CRAVECARE_PROFILE_DB
env overrides so tests never touch the real db files) BEFORE the app UI
exists, per the two-pass discipline: these encode the spec's state-mutation
and selection-flow contract, and the implementation in Step 3 must satisfy
them, not the other way around.
"""
import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    """Point the app at an isolated, freshly-seeded cache + profile db."""
    from scripts.seed_cache import seed

    cache_db = tmp_path / "cache.db"
    profile_db = tmp_path / "profile.db"
    fixtures = Path(__file__).resolve().parent.parent / "fixtures" / "raw_sources.json"
    seed(cache_db, fixtures)
    monkeypatch.setenv("CRAVECARE_CACHE_DB", str(cache_db))
    monkeypatch.setenv("CRAVECARE_PROFILE_DB", str(profile_db))
    return {"cache_db": cache_db, "profile_db": profile_db}


def run_app(app_env) -> AppTest:
    at = AppTest.from_file(APP_PATH)
    at.run()
    return at


def test_app_loads_without_exception(app_env):
    at = run_app(app_env)
    assert not at.exception


def test_zero_selection_default_feed_populates_on_load(app_env):
    """§2.1: on first load with no selections, feed auto-populates."""
    at = run_app(app_env)
    assert not at.exception
    body_text = " ".join(md.value for md in at.markdown) + " ".join(h.value for h in at.header) + " ".join(s.value for s in at.subheader)
    assert "default feed" in body_text.lower()


def test_profile_panel_shows_hard_no_labels(app_env):
    """§4.1: Right panel contains locked checkboxes for the three hard NOs."""
    at = run_app(app_env)
    checkbox_labels = [cb.label for cb in at.checkbox]
    assert any("Mushrooms" in label for label in checkbox_labels)
    assert any("Bell Peppers" in label for label in checkbox_labels)
    assert any("Overly Oily" in label for label in checkbox_labels)


def test_hard_no_checkboxes_are_prechecked_by_default(app_env):
    at = run_app(app_env)
    hard_no_boxes = [cb for cb in at.checkbox if cb.label in (
        "Mushrooms", "Bell Peppers (Capsicum)", "Overly Oily Gravies"
    )]
    assert len(hard_no_boxes) == 3
    assert all(cb.value is True for cb in hard_no_boxes)


def test_session_overrides_default_off(app_env):
    """§3A: session-only overrides reset to OFF every new session."""
    at = run_app(app_env)
    override_boxes = [cb for cb in at.checkbox if cb.label in (
        "No Dairy / Cream today", "Skip Rice dishes"
    )]
    assert len(override_boxes) == 2
    assert all(cb.value is False for cb in override_boxes)


def test_cuisine_selection_updates_state(app_env):
    """State mutation: selecting a cuisine button updates session state."""
    at = run_app(app_env)
    chinese_button = next(b for b in at.button if b.label == "Chinese")
    chinese_button.click().run()
    assert not at.exception
    assert at.session_state["selected_cuisine"] == "Chinese"


def test_show_curated_meals_button_triggers_recommendation(app_env):
    """Selection flow: cuisine -> drink -> dessert -> Show Curated Meals CTA."""
    at = run_app(app_env)
    chinese_button = next(b for b in at.button if b.label == "Chinese")
    chinese_button.click().run()

    show_button = next(b for b in at.button if "Show My Curated Meal" in b.label)
    show_button.click().run()

    assert not at.exception
    assert at.session_state["curated_meals_result"] is not None
    assert len(at.session_state["curated_meals_result"]) >= 1


def test_no_dairy_override_excludes_dairy_items_from_curated_result(app_env):
    at = run_app(app_env)
    chinese_button = next(b for b in at.button if b.label == "North Indian")
    chinese_button.click().run()

    no_dairy_box = next(cb for cb in at.checkbox if cb.label == "No Dairy / Cream today")
    no_dairy_box.set_value(True).run()

    show_button = next(b for b in at.button if "Show My Curated Meal" in b.label)
    show_button.click().run()

    assert not at.exception
    result = at.session_state["curated_meals_result"]
    all_dish_names = [item.dish_name for meal in result for item in meal.items]
    assert "Dal Makhani + Butter Naan" not in all_dish_names


def test_editing_hard_no_list_persists_only_on_explicit_save(app_env):
    """§3A: writes only on explicit user action, not every interaction."""
    at = run_app(app_env)
    mushroom_box = next(cb for cb in at.checkbox if cb.label == "Mushrooms")
    mushroom_box.set_value(False).run()
    assert not at.exception
    # Re-running a fresh AppTest instance (simulating a new page load without
    # an explicit save) should still show the original persisted default.
    at2 = run_app(app_env)
    mushroom_box2 = next(cb for cb in at2.checkbox if cb.label == "Mushrooms")
    assert mushroom_box2.value is True
