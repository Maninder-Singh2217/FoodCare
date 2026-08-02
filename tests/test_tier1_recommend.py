"""Tier 1: selection flow & recommendation logic tests (§2.1, §2.2), against fixtures."""
from cravecare import cache as cache_module
from cravecare.filters import SessionOverrides
from cravecare.persistence import Profile
from cravecare.recommend import curated_meals, zero_selection_feed


def test_zero_selection_feed_returns_three_picks(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn, area="Bandra West")
    profile = Profile()
    picks = zero_selection_feed(items, profile.hard_no_list, SessionOverrides(), profile)
    labels = [p.label for p in picks]
    assert "Reddit / Local Gem Pick" in labels
    assert "Fast Delivery Pick" in labels
    assert "Sweet Cravings Pick" in labels


def test_zero_selection_feed_fast_pick_within_threshold(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn, area="Bandra West")
    profile = Profile()
    picks = zero_selection_feed(items, profile.hard_no_list, SessionOverrides(), profile)
    fast_pick = next(p for p in picks if p.label == "Fast Delivery Pick")
    assert all(i.prep_delivery_minutes <= 30 for i in fast_pick.items)


def test_zero_selection_feed_respects_hard_nos(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn, area="Bandra West")
    profile = Profile()
    picks = zero_selection_feed(items, profile.hard_no_list, SessionOverrides(), profile)
    all_dishes = [i.dish_name for p in picks for i in p.items]
    assert "Mushroom Manchurian" not in all_dishes
    assert "Extra Oily Butter Chicken Gravy" not in all_dishes


def test_zero_selection_sweet_pick_uses_current_rotation_index(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn, area="Bandra West")
    profile = Profile()
    profile.dessert_rotation_index = 2  # -> "Warm Fudgy Brownie"
    profile.drink_rotation_index = 0  # -> "Masala Chai"
    picks = zero_selection_feed(items, profile.hard_no_list, SessionOverrides(), profile)
    sweet_pick = next(p for p in picks if p.label == "Sweet Cravings Pick")
    dish_names = {i.dish_name for i in sweet_pick.items}
    assert "Warm Fudgy Brownie" in dish_names
    assert "Masala Chai" in dish_names


def test_curated_meals_filters_by_cuisine(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn, area="Bandra West")
    profile = Profile()
    result = curated_meals(
        items, profile.hard_no_list, SessionOverrides(), profile,
        cuisine="Chinese", drink_label=None, dessert_choice=None,
    )
    assert len(result) == 1
    main_dish_names = [i.dish_name for i in result[0].items]
    # Main item must be Chinese cuisine and pass hard-NOs (Mushroom Manchurian excluded)
    assert "Veg Hakka Noodles" in main_dish_names
    assert "Mushroom Manchurian" not in main_dish_names


def test_curated_meals_surprise_me_ignores_cuisine_filter(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn, area="Bandra West")
    profile = Profile()
    result = curated_meals(
        items, profile.hard_no_list, SessionOverrides(), profile,
        cuisine="Surprise Me", drink_label=None, dessert_choice=None,
    )
    assert len(result) == 1
    assert len(result[0].items) >= 1


def test_curated_meals_dessert_skip_omits_dessert(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn, area="Bandra West")
    profile = Profile()
    result = curated_meals(
        items, profile.hard_no_list, SessionOverrides(), profile,
        cuisine="Chinese", drink_label=None, dessert_choice="Skip",
    )
    dish_names = [i.dish_name for i in result[0].items]
    from cravecare.recommend import DESSERT_POOL_NAMES
    assert not any(name in DESSERT_POOL_NAMES for name in dish_names)


def test_curated_meals_explicit_drink_choice_used(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn, area="Bandra West")
    profile = Profile()
    result = curated_meals(
        items, profile.hard_no_list, SessionOverrides(), profile,
        cuisine="North Indian", drink_label="Cold / None", dessert_choice="Skip",
    )
    dish_names = [i.dish_name for i in result[0].items]
    assert "Peach Iced Tea" in dish_names


def test_curated_meals_returns_empty_when_cuisine_has_no_eligible_items(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn, area="Powai")
    profile = Profile()
    result = curated_meals(
        items, profile.hard_no_list, SessionOverrides(), profile,
        cuisine="Sindhi Comfort", drink_label=None, dessert_choice=None,
    )
    assert result == []


def test_rotation_index_advances_and_wraps(seeded_cache_conn):
    profile = Profile()
    pool_len = len(profile.dessert_rotation_pool)
    for _ in range(pool_len):
        profile.advance_dessert()
    assert profile.dessert_rotation_index == 0  # wrapped back to start
