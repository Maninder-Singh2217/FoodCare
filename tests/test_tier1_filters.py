"""Tier 1: Hard & Soft Filtering Logic tests (§2.3), against seeded fixture cache."""
from cravecare import cache as cache_module
from cravecare.filters import (
    SessionOverrides,
    apply_filters,
    passes_all_filters,
    violates_delivery_threshold,
    violates_hard_no,
    violates_session_overrides,
)
from cravecare.persistence import DEFAULT_HARD_NOS


def _find(items, dish_name):
    return next(i for i in items if i.dish_name == dish_name)


def test_hard_no_mushrooms_excludes_item(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn)
    manchurian = _find(items, "Mushroom Manchurian")
    assert violates_hard_no(manchurian, DEFAULT_HARD_NOS) is True


def test_hard_no_bell_peppers_excludes_item(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn)
    wrap = _find(items, "Paneer Tikka Wrap")
    assert violates_hard_no(wrap, DEFAULT_HARD_NOS) is True


def test_hard_no_overly_oily_gravy_excludes_item(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn)
    gravy = _find(items, "Extra Oily Butter Chicken Gravy")
    assert violates_hard_no(gravy, DEFAULT_HARD_NOS) is True


def test_hard_no_does_not_exclude_unrelated_item(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn)
    noodles = _find(items, "Veg Hakka Noodles")
    assert violates_hard_no(noodles, DEFAULT_HARD_NOS) is False


def test_hard_no_list_editable_no_longer_excludes_when_removed(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn)
    manchurian = _find(items, "Mushroom Manchurian")
    reduced_list = [n for n in DEFAULT_HARD_NOS if n != "Mushrooms"]
    assert violates_hard_no(manchurian, reduced_list) is False


def test_session_override_no_dairy_excludes_dairy_item(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn)
    dal = _find(items, "Dal Makhani + Butter Naan")
    overrides = SessionOverrides(no_dairy_today=True)
    assert violates_session_overrides(dal, overrides) is True


def test_session_override_off_by_default(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn)
    dal = _find(items, "Dal Makhani + Butter Naan")
    overrides = SessionOverrides()  # defaults OFF per §3A
    assert violates_session_overrides(dal, overrides) is False


def test_session_override_skip_rice_excludes_rice_item(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn)
    sai_bhaji = _find(items, "Sai Bhaji + Rice")
    overrides = SessionOverrides(skip_rice=True)
    assert violates_session_overrides(sai_bhaji, overrides) is True


def test_fast_delivery_only_excludes_slow_items(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn)
    slow_gravy = _find(items, "Extra Oily Butter Chicken Gravy")  # 40 min
    overrides = SessionOverrides(fast_delivery_only=True, fast_delivery_minutes=30)
    assert violates_delivery_threshold(slow_gravy, overrides) is True


def test_fast_delivery_only_allows_fast_items(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn)
    wrap = _find(items, "Paneer Tikka Wrap")  # 15 min
    overrides = SessionOverrides(fast_delivery_only=True, fast_delivery_minutes=30)
    assert violates_delivery_threshold(wrap, overrides) is False


def test_filter_order_hard_no_checked_first_even_if_overrides_would_pass(seeded_cache_conn):
    """§2.3: hard NOs checked before session overrides - a hard-NO item must
    never pass even if session overrides wouldn't have excluded it."""
    items = cache_module.read_all(seeded_cache_conn)
    manchurian = _find(items, "Mushroom Manchurian")
    overrides = SessionOverrides()  # no active session overrides
    assert passes_all_filters(manchurian, DEFAULT_HARD_NOS, overrides) is False


def test_apply_filters_combines_all_three_checks(seeded_cache_conn):
    items = cache_module.read_all(seeded_cache_conn)
    overrides = SessionOverrides(no_dairy_today=True, fast_delivery_only=True, fast_delivery_minutes=30)
    result = apply_filters(items, DEFAULT_HARD_NOS, overrides)
    names = {i.dish_name for i in result}
    assert "Mushroom Manchurian" not in names  # hard no
    assert "Dal Makhani + Butter Naan" not in names  # dairy override
    assert "Extra Oily Butter Chicken Gravy" not in names  # hard no + slow
    assert "Veg Hakka Noodles" in names  # passes everything
