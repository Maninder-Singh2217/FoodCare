"""Recommendation logic per spec §2.1, §2.2, §2.4-adjacent selection flow.

Two entry points:
  - zero_selection_feed: §2.1, auto-populated 3-pick feed on first load.
  - curated_meals: cuisine/drink/dessert selection -> filtered, scored bundle.
"""
from dataclasses import dataclass

from cravecare.cache import CachedItem
from cravecare.filters import SessionOverrides, apply_filters
from cravecare.persistence import Profile

FAST_DELIVERY_CEILING_MINUTES = 30  # §2.1 pick 2: "<25-30 mins"

DRINK_LABEL_TO_DISH_NAMES = {
    "Hot (Chai / Hot Choc)": ["Masala Chai", "Hot Chocolate"],
    "Warm (Soups / Teas)": ["Warm Honey Lemon Water"],
    "Cold / None": ["Peach Iced Tea"],
}
DESSERT_POOL_NAMES = {
    "Nutella Dark Chocolate Waffle", "Blueberry Cream Cheese Waffle",
    "Warm Fudgy Brownie", "Gulab Jamun",
}
DRINK_POOL_NAMES = {
    "Masala Chai", "Hot Chocolate", "Warm Honey Lemon Water", "Peach Iced Tea",
}


@dataclass
class CuratedMeal:
    label: str
    items: list[CachedItem]


def zero_selection_feed(
    items: list[CachedItem], hard_no_list: list[str], overrides: SessionOverrides, profile: Profile
) -> list[CuratedMeal]:
    """§2.1: 3 high-confidence picks with no user selection, filtered per §2.3."""
    eligible = apply_filters(items, hard_no_list, overrides)
    if not eligible:
        return []

    non_dessert_drink = [i for i in eligible if i.dish_name not in DESSERT_POOL_NAMES and i.dish_name not in DRINK_POOL_NAMES]
    desserts = [i for i in eligible if i.dish_name in DESSERT_POOL_NAMES]
    drinks = [i for i in eligible if i.dish_name in DRINK_POOL_NAMES]

    picks: list[CuratedMeal] = []

    # Pick 1: Reddit/Local Gem — highest quality_score backed by reddit mentions.
    reddit_backed = [i for i in non_dessert_drink if i.reddit_score is not None]
    pool_for_pick1 = reddit_backed or non_dessert_drink
    if pool_for_pick1:
        top = max(pool_for_pick1, key=lambda i: i.quality_score)
        picks.append(CuratedMeal("Reddit / Local Gem Pick", [top]))

    # Pick 2: Fast Delivery — highest-rated within delivery ceiling.
    fast_candidates = [i for i in non_dessert_drink if i.prep_delivery_minutes <= FAST_DELIVERY_CEILING_MINUTES]
    if fast_candidates:
        fastest_best = max(fast_candidates, key=lambda i: i.quality_score)
        picks.append(CuratedMeal("Fast Delivery Pick", [fastest_best]))

    # Pick 3: Sweet Cravings — rotated dessert + a warm/light item.
    sweet_bundle: list[CachedItem] = []
    if desserts:
        rotated_dessert_name = profile.next_dessert()
        dessert_item = next((d for d in desserts if d.dish_name == rotated_dessert_name), None) or max(
            desserts, key=lambda i: i.quality_score
        )
        sweet_bundle.append(dessert_item)
    if drinks:
        rotated_drink_name = profile.next_drink()
        drink_item = next((d for d in drinks if d.dish_name == rotated_drink_name), None) or max(
            drinks, key=lambda i: i.quality_score
        )
        sweet_bundle.append(drink_item)
    if sweet_bundle:
        picks.append(CuratedMeal("Sweet Cravings Pick", sweet_bundle))

    return picks


def curated_meals(
    items: list[CachedItem],
    hard_no_list: list[str],
    overrides: SessionOverrides,
    profile: Profile,
    cuisine: str | None,
    drink_label: str | None,
    dessert_choice: str | None,
) -> list[CuratedMeal]:
    """Selection-flow path: cuisine/drink/dessert -> curated bundle (§2, §2.2).

    - cuisine: one of the Step 1 options, or None/"Surprise Me".
    - drink_label: one of the Step 2 option labels, or None for auto-rotate.
    - dessert_choice: "Rotate Her Favs", "Skip", or None (treated as rotate).
    """
    eligible = apply_filters(items, hard_no_list, overrides)
    if not eligible:
        return []

    main_pool = [i for i in eligible if i.dish_name not in DESSERT_POOL_NAMES and i.dish_name not in DRINK_POOL_NAMES]

    if cuisine and cuisine != "Surprise Me":
        cuisine_matches = [i for i in main_pool if i.cuisine == cuisine]
    else:
        cuisine_matches = main_pool

    if not cuisine_matches:
        return []

    main_item = max(cuisine_matches, key=lambda i: i.quality_score)
    bundle = [main_item]

    # §2.2: drink/dessert auto-addition from rotation pool when left on auto-rotate.
    drinks = [i for i in eligible if i.dish_name in DRINK_POOL_NAMES]
    desserts = [i for i in eligible if i.dish_name in DESSERT_POOL_NAMES]

    if drink_label and drink_label in DRINK_LABEL_TO_DISH_NAMES:
        wanted_names = DRINK_LABEL_TO_DISH_NAMES[drink_label]
        drink_item = next((d for d in drinks if d.dish_name in wanted_names), None)
        if drink_item:
            bundle.append(drink_item)
    elif drink_label is None and drinks:
        rotated_name = profile.next_drink()
        drink_item = next((d for d in drinks if d.dish_name == rotated_name), None) or drinks[0]
        bundle.append(drink_item)

    if dessert_choice == "Skip":
        pass
    elif desserts:
        rotated_name = profile.next_dessert()
        dessert_item = next((d for d in desserts if d.dish_name == rotated_name), None) or desserts[0]
        bundle.append(dessert_item)

    return [CuratedMeal("Curated Meal", bundle)]
