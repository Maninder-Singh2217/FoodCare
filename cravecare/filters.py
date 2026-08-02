"""Hard & Soft Filtering Logic per spec §2.3.

Every candidate item is checked, in order:
  (1) Permanent Hard NOs
  (2) Active Session Overrides (dairy/rice if checked today)
  (3) Delivery time threshold (Fast Delivery Only)
"""
from dataclasses import dataclass

from cravecare.cache import CachedItem

HARD_NO_TAG_MAP = {
    "Mushrooms": "contains_mushrooms",
    "Bell Peppers (Capsicum)": "contains_bell_peppers",
    "Overly Oily Gravies": "overly_oily_gravy",
}


@dataclass
class SessionOverrides:
    no_dairy_today: bool = False
    skip_rice: bool = False
    fast_delivery_only: bool = False
    fast_delivery_minutes: int = 40  # slider default per §1.2, range up to 60


def violates_hard_no(item: CachedItem, hard_no_list: list[str]) -> bool:
    """§2.3 step 1."""
    active_tags = {HARD_NO_TAG_MAP[name] for name in hard_no_list if name in HARD_NO_TAG_MAP}
    return bool(active_tags.intersection(item.tags))


def violates_session_overrides(item: CachedItem, overrides: SessionOverrides) -> bool:
    """§2.3 step 2."""
    if overrides.no_dairy_today and "contains_dairy" in item.tags:
        return True
    if overrides.skip_rice and "contains_rice" in item.tags:
        return True
    return False


def violates_delivery_threshold(item: CachedItem, overrides: SessionOverrides) -> bool:
    """§2.3 step 3."""
    if overrides.fast_delivery_only and item.prep_delivery_minutes > overrides.fast_delivery_minutes:
        return True
    return False


def passes_all_filters(item: CachedItem, hard_no_list: list[str], overrides: SessionOverrides) -> bool:
    """Applies §2.3's three checks in order; short-circuits on first failure."""
    if violates_hard_no(item, hard_no_list):
        return False
    if violates_session_overrides(item, overrides):
        return False
    if violates_delivery_threshold(item, overrides):
        return False
    return True


def apply_filters(items: list[CachedItem], hard_no_list: list[str], overrides: SessionOverrides) -> list[CachedItem]:
    return [item for item in items if passes_all_filters(item, hard_no_list, overrides)]
