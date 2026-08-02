"""CraveCare - Streamlit app. See cravecare_spec_v1.1_merged.md for the full spec.

Section references (§) throughout point back to that spec.
"""
import os
from pathlib import Path

import streamlit as st

from cravecare import cache as cache_module
from cravecare import persistence as persistence_module
from cravecare.deeplinks import render_deep_link_snippet, swiggy_web_url, zomato_web_url
from cravecare.filters import SessionOverrides
from cravecare.recommend import CuratedMeal, curated_meals, zero_selection_feed

st.set_page_config(page_title="CraveCare", page_icon="\U0001F37D️", layout="wide")

CACHE_DB_PATH = Path(os.environ.get("CRAVECARE_CACHE_DB", cache_module.DEFAULT_CACHE_PATH))
PROFILE_DB_PATH = Path(os.environ.get("CRAVECARE_PROFILE_DB", persistence_module.DEFAULT_DB_PATH))

CUISINE_OPTIONS = [
    "Chinese", "North Indian", "South Indian", "Sindhi Comfort",
    "Fast Food", "Street Food", "Pizza", "Burgers", "Rolls & Wraps",
    "Surprise Me",
]
CUISINE_BUTTONS_PER_ROW = 5
DRINK_OPTIONS = ["Auto (Rotate)", "Hot (Chai / Hot Choc)", "Warm (Soups / Teas)", "Cold / None"]
DESSERT_OPTIONS = ["Rotate Her Favs", "Skip"]


def get_cache_conn():
    return cache_module.get_connection(CACHE_DB_PATH)


def get_profile_conn():
    return persistence_module.get_connection(PROFILE_DB_PATH)


def init_state():
    if "initialized" in st.session_state:
        return
    conn = get_profile_conn()
    profile = persistence_module.load_profile(conn)
    conn.close()

    st.session_state.initialized = True
    st.session_state.profile = profile
    st.session_state.session_location = profile.default_location
    st.session_state.selected_cuisine = None
    st.session_state.selected_drink = "Auto (Rotate)"
    st.session_state.selected_dessert = "Rotate Her Favs"
    st.session_state.curated_meals_result = None
    st.session_state.profile_sheet_open = False

    # §3A: session-only overrides, default OFF every new session, never persisted.
    st.session_state.override_no_dairy = False
    st.session_state.override_skip_rice = False
    st.session_state.override_fast_delivery_only = False
    st.session_state.override_fast_delivery_minutes = 40

    # §3A editable hard-NO list, seeded from persisted profile.
    for name in persistence_module.DEFAULT_HARD_NOS:
        key = f"hardno_{name}"
        if key not in st.session_state:
            st.session_state[key] = name in profile.hard_no_list


def current_hard_no_list() -> list[str]:
    return [
        name for name in persistence_module.DEFAULT_HARD_NOS
        if st.session_state.get(f"hardno_{name}", True)
    ]


def current_overrides() -> SessionOverrides:
    return SessionOverrides(
        no_dairy_today=st.session_state.override_no_dairy,
        skip_rice=st.session_state.override_skip_rice,
        fast_delivery_only=st.session_state.override_fast_delivery_only,
        fast_delivery_minutes=st.session_state.override_fast_delivery_minutes,
    )


def load_area_items(area: str):
    conn = get_cache_conn()
    items = cache_module.read_all(conn, area=area)
    last_updated = cache_module.latest_updated_at(conn)
    conn.close()
    return items, last_updated


def render_meal_card(item, key_suffix: str = ""):
    with st.container(border=True):
        st.markdown(f"**{item.dish_name}** — _{item.restaurant_name}_")
        st.caption(
            f"{item.cuisine} · ⭐ {item.quality_score:.2f} quality score · "
            f"🚴 {item.prep_delivery_minutes} min delivery"
        )
        swiggy_url = swiggy_web_url(item.restaurant_id)
        zomato_url = zomato_web_url(item.restaurant_id)
        st.iframe(
            render_deep_link_snippet(
                item.restaurant_id, swiggy_url, zomato_url,
                container_id_suffix=f"-{item.dish_id}{key_suffix}",
            ),
            height=60,
        )


def render_curated_meal(meal: CuratedMeal, key_suffix: str = ""):
    st.markdown(f"#### {meal.label}")
    for item in meal.items:
        render_meal_card(item, key_suffix=f"{key_suffix}-{item.dish_id}")


def render_profile_panel_contents():
    st.subheader("\U0001F464 Shweta's Saved Profile")
    st.write(f"\U0001F4CD Location: {st.session_state.session_location}")

    st.markdown("**\U0001F6AB Permanent Hard NOs**")
    for name in persistence_module.DEFAULT_HARD_NOS:
        st.checkbox(name, key=f"hardno_{name}")

    if st.button("Save Hard NOs as default", key="save_hard_nos_btn"):
        conn = get_profile_conn()
        profile = persistence_module.load_profile(conn)
        profile.hard_no_list = current_hard_no_list()
        persistence_module.save_profile(conn, profile)
        conn.close()
        st.success("Saved.")

    st.markdown("**\U0001F9C7 Dessert Rotation Favorites**")
    st.caption("\"Rotate Her Favs\" cycles through whichever desserts you pick here.")
    selected_desserts = st.multiselect(
        "Desserts to rotate through",
        options=persistence_module.DEFAULT_DESSERT_POOL,
        default=[d for d in st.session_state.profile.dessert_rotation_pool
                 if d in persistence_module.DEFAULT_DESSERT_POOL],
        key="dessert_favs_multiselect",
        label_visibility="collapsed",
    )
    if st.button("Save dessert favorites", key="save_dessert_favs_btn"):
        if not selected_desserts:
            st.error("Pick at least one dessert to rotate through.")
        else:
            conn = get_profile_conn()
            profile = persistence_module.load_profile(conn)
            profile.dessert_rotation_pool = selected_desserts
            profile.dessert_rotation_index = 0
            persistence_module.save_profile(conn, profile)
            conn.close()
            st.session_state.profile = profile
            st.success("Saved.")

    st.markdown("**⚡ Exclude Today Only?**")
    st.checkbox("No Dairy / Cream today", key="override_no_dairy")
    st.checkbox("Skip Rice dishes", key="override_skip_rice")
    st.checkbox("Fast Delivery Only (<30m)", key="override_fast_delivery_only")
    if st.session_state.override_fast_delivery_only:
        st.slider(
            "Fast delivery ceiling (minutes)", min_value=10, max_value=60,
            key="override_fast_delivery_minutes",
        )

    st.markdown("**Override Location for Session**")
    new_location = st.selectbox(
        "Area", persistence_module.KNOWN_AREAS,
        index=persistence_module.KNOWN_AREAS.index(st.session_state.session_location)
        if st.session_state.session_location in persistence_module.KNOWN_AREAS else 0,
        key="location_selectbox",
    )
    st.session_state.session_location = new_location
    save_as_default = st.checkbox("Save as my new default location", key="save_location_default")
    if save_as_default:
        conn = get_profile_conn()
        profile = persistence_module.load_profile(conn)
        profile.default_location = new_location
        persistence_module.save_profile(conn, profile)
        conn.close()

    st.markdown("---")
    st.markdown("**\U0001F527 Admin**")
    if st.button("\U0001F504 Refresh recommendations", key="refresh_cache_btn"):
        from scripts.seed_cache import seed

        seed(CACHE_DB_PATH)
        st.success("Recommendation cache refreshed.")
        st.rerun()


APP_BACKGROUND = "#EFE7D9"  # Soft Linen
APP_CARD_BACKGROUND = "#FAF7F0"  # slightly lighter, so cards lift off the background
APP_TEXT_COLOR = "#3A362E"  # warm dark brown-gray for contrast against the cream
APP_MUTED_TEXT_COLOR = "#6B6455"
APP_BUTTON_COLOR = "#6B4423"  # woodish brown, replaces default black for visibility on beige
APP_BUTTON_HOVER_COLOR = "#4A2E17"  # darker wood tone for hover/active state


def render_global_theme():
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-color: {APP_BACKGROUND};
        }}
        .stApp, .stApp p, .stApp span, .stApp div, .stApp label,
        .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {{
            color: {APP_TEXT_COLOR};
        }}
        .stApp [data-testid="stCaptionContainer"], .stApp small {{
            color: {APP_MUTED_TEXT_COLOR} !important;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background-color: {APP_CARD_BACKGROUND};
            border-radius: 8px;
        }}
        div[data-testid="stColumn"]:has(.cravecare-profile-marker) {{
            background-color: {APP_BACKGROUND};
        }}
        .stApp button[data-testid^="stBaseButton-secondary"] {{
            color: {APP_BUTTON_COLOR} !important;
            border-color: {APP_BUTTON_COLOR} !important;
            background-color: {APP_CARD_BACKGROUND} !important;
        }}
        .stApp button[data-testid^="stBaseButton-secondary"]:hover,
        .stApp button[data-testid^="stBaseButton-secondary"]:focus {{
            color: {APP_BUTTON_HOVER_COLOR} !important;
            border-color: {APP_BUTTON_HOVER_COLOR} !important;
            background-color: {APP_BACKGROUND} !important;
        }}
        .stApp button[data-testid^="stBaseButton-secondary"] p {{
            color: {APP_BUTTON_COLOR} !important;
        }}
        .stApp button[data-testid^="stBaseButton-secondary"]:hover p,
        .stApp button[data-testid^="stBaseButton-secondary"]:focus p {{
            color: {APP_BUTTON_HOVER_COLOR} !important;
        }}
        [data-testid="stCheckbox"] label:not([data-selected="true"]) > div:first-of-type {{
            background-color: {APP_CARD_BACKGROUND} !important;
            border-color: {APP_BUTTON_COLOR} !important;
        }}
        [data-testid="stRadio"] label:not([data-selected="true"]) > div > div div {{
            background-color: {APP_CARD_BACKGROUND} !important;
            border-color: {APP_BUTTON_COLOR} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def main():
    init_state()
    render_global_theme()

    header_col1, header_col2 = st.columns([5, 1])
    with header_col1:
        st.markdown(f"### \U0001F4CD {st.session_state.session_location}, Mumbai")
    with header_col2:
        if st.button("\U0001F464", key="profile_icon_btn", help="Profile & Overrides"):
            st.session_state.profile_sheet_open = not st.session_state.profile_sheet_open

    is_mobile_sheet_open = st.session_state.profile_sheet_open
    st.markdown(
        f"""
        <style>
        @media (max-width: 768px) {{
          div[data-testid="stColumn"]:has(.cravecare-profile-marker) {{
            {f"display:block !important; position:fixed !important; bottom:0; left:0; right:0; top:auto; width:100% !important; max-width:100% !important; z-index:9999; background:{APP_BACKGROUND}; max-height:80vh; overflow-y:auto; box-shadow:0 -2px 12px rgba(0,0,0,0.3); border-radius:16px 16px 0 0; padding:1rem;" if is_mobile_sheet_open else "display:none !important;"}
          }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    desktop_main, desktop_sidebar = st.columns([3, 1])

    with desktop_main:
        st.markdown("#### \U0001F4CD STEP 1: Cuisine Choice")
        for row_start in range(0, len(CUISINE_OPTIONS), CUISINE_BUTTONS_PER_ROW):
            row_options = CUISINE_OPTIONS[row_start:row_start + CUISINE_BUTTONS_PER_ROW]
            cuisine_cols = st.columns(CUISINE_BUTTONS_PER_ROW)
            for col, cuisine in zip(cuisine_cols, row_options):
                with col:
                    if st.button(cuisine, key=f"cuisine_{cuisine}"):
                        st.session_state.selected_cuisine = cuisine

        if st.session_state.selected_cuisine:
            st.caption(f"Selected: {st.session_state.selected_cuisine}")

        st.markdown("#### ☕ STEP 2: Drink Preference")
        st.session_state.selected_drink = st.radio(
            "Drink", DRINK_OPTIONS, index=DRINK_OPTIONS.index(st.session_state.selected_drink),
            key="drink_radio", label_visibility="collapsed",
        )

        st.markdown("#### \U0001F9C7 STEP 3: Dessert")
        st.session_state.selected_dessert = st.radio(
            "Dessert", DESSERT_OPTIONS, index=DESSERT_OPTIONS.index(st.session_state.selected_dessert),
            key="dessert_radio", label_visibility="collapsed",
        )

        st.markdown("---")
        if st.button("\U0001F31F Show My Curated Meal Options", key="show_curated_btn", type="primary"):
            items, _ = load_area_items(st.session_state.session_location)
            drink_label = None if st.session_state.selected_drink == "Auto (Rotate)" else st.session_state.selected_drink
            dessert_choice = st.session_state.selected_dessert
            result = curated_meals(
                items,
                current_hard_no_list(),
                current_overrides(),
                st.session_state.profile,
                cuisine=st.session_state.selected_cuisine,
                drink_label=drink_label,
                dessert_choice=None if dessert_choice == "Rotate Her Favs" else dessert_choice,
            )
            st.session_state.curated_meals_result = result

            # Advance rotation for pools used on auto-rotate this run.
            if drink_label is None:
                st.session_state.profile.advance_drink()
            if dessert_choice != "Skip":
                st.session_state.profile.advance_dessert()

        if st.session_state.curated_meals_result:
            st.markdown("### Curated Meals")
            for i, meal in enumerate(st.session_state.curated_meals_result):
                render_curated_meal(meal, key_suffix=f"curated-{i}")

        st.markdown("---")
        st.markdown("#### \U0001F6D1 Your Default Feed")
        items, last_updated = load_area_items(st.session_state.session_location)
        default_feed = zero_selection_feed(
            items, current_hard_no_list(), current_overrides(), st.session_state.profile
        )
        if last_updated:
            st.caption(f"Cache last updated: {last_updated}")
        for i, meal in enumerate(default_feed):
            render_curated_meal(meal, key_suffix=f"default-{i}")

    with desktop_sidebar:
        st.markdown('<span class="cravecare-profile-marker"></span>', unsafe_allow_html=True)
        render_profile_panel_contents()


main()
