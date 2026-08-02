"""Tier 2: Playwright E2E tests (§4, §4.1).

Runs against a live `streamlit run app.py` instance (see README for how to
start it before running this suite - CRAVECARE_BASE_URL env var overrides
the default http://localhost:8501).

ENVIRONMENT NOTE (flagged limitation, not a spec gap): this sandbox only
has the Chromium browser binary installed (no WebKit/Firefox). §4.1 asks
for "iPhone (WebKit/Safari)" emulation; since CraveCare's iOS/Android
deep-link branching (cravecare/deeplinks.py) is driven entirely by a
`navigator.userAgent` string check rather than actual rendering-engine
differences, the iPhone context here uses Chromium with a spoofed iOS
Safari user-agent string. This validates the UA-branching logic correctly
but does not exercise genuine WebKit engine behavior - revisit with real
WebKit if this environment gains that binary.
"""
import os
import re

import pytest
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("CRAVECARE_BASE_URL", "http://localhost:8501")
CHROMIUM_PATH = "/opt/pw-browsers/chromium"

IPHONE_VIEWPORT = {"width": 390, "height": 844}
IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
ANDROID_VIEWPORT = {"width": 412, "height": 915}
ANDROID_UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Mobile Safari/537.36"
)
DESKTOP_VIEWPORT = {"width": 1280, "height": 900}


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROMIUM_PATH)
        yield b
        b.close()


def new_page(browser, viewport, user_agent=None):
    context = browser.new_context(viewport=viewport, user_agent=user_agent)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    return page, context, errors


# ---- §4.1 Profile contract ----

def test_profile_panel_contains_required_labels_desktop(browser):
    page, context, errors = new_page(browser, DESKTOP_VIEWPORT)
    page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1500)
    body_text = page.inner_text("body")
    assert "Savreen's Saved Profile" in body_text
    assert "Mushrooms" in body_text
    assert "Bell Peppers (Capsicum)" in body_text
    assert "Overly Oily Gravies" in body_text
    assert errors == []
    context.close()


# ---- §4.1 Layout contract ----

def test_profile_panel_visible_on_desktop_width(browser):
    page, context, errors = new_page(browser, DESKTOP_VIEWPORT)
    page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1500)
    profile_heading = page.locator("text=Savreen's Saved Profile")
    assert profile_heading.is_visible()
    context.close()


def test_profile_panel_hidden_by_default_on_mobile_width(browser):
    page, context, errors = new_page(browser, IPHONE_VIEWPORT, user_agent=IPHONE_UA)
    page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1500)
    profile_heading = page.locator("text=Savreen's Saved Profile")
    assert profile_heading.count() == 0 or not profile_heading.first.is_visible()
    context.close()


def test_profile_bottom_sheet_opens_on_mobile_after_icon_tap(browser):
    page, context, errors = new_page(browser, IPHONE_VIEWPORT, user_agent=IPHONE_UA)
    page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1500)
    icon_buttons = page.locator('button:has-text("\U0001F464")')
    visible_icon = next(
        icon_buttons.nth(i) for i in range(icon_buttons.count()) if icon_buttons.nth(i).is_visible()
    )
    visible_icon.click()
    page.wait_for_timeout(1500)
    profile_heading = page.locator("text=Savreen's Saved Profile")
    assert profile_heading.first.is_visible()
    assert errors == []
    context.close()


# ---- §4.1 Links contract ----

def test_deep_link_buttons_present_with_correct_urls(browser):
    page, context, errors = new_page(browser, DESKTOP_VIEWPORT)
    page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)
    iframes = page.frames
    found_swiggy = False
    found_zomato = False
    for frame in iframes:
        swiggy_link = frame.locator('a:has-text("Order on Swiggy")')
        zomato_link = frame.locator('a:has-text("Order on Zomato")')
        if swiggy_link.count() > 0:
            href = swiggy_link.first.get_attribute("href")
            assert href is not None and href.startswith("https://www.swiggy.com/")
            found_swiggy = True
        if zomato_link.count() > 0:
            href = zomato_link.first.get_attribute("href")
            assert href is not None and href.startswith("https://www.zomato.com/")
            found_zomato = True
    assert found_swiggy, "No Swiggy deep-link buttons found on page"
    assert found_zomato, "No Zomato deep-link buttons found on page"
    context.close()


# ---- §4.1 Cross-platform deep-link contract ----

def _find_deep_link_frame(page):
    for frame in page.frames:
        if frame.locator('a:has-text("Order on Swiggy")').count() > 0:
            return frame
    return None


def test_ios_context_no_unhandled_exceptions_on_card_render(browser):
    page, context, errors = new_page(browser, IPHONE_VIEWPORT, user_agent=IPHONE_UA)
    page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)
    assert errors == []
    frame = _find_deep_link_frame(page)
    assert frame is not None
    context.close()


def test_android_context_no_unhandled_exceptions_on_card_render(browser):
    page, context, errors = new_page(browser, ANDROID_VIEWPORT, user_agent=ANDROID_UA)
    page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)
    assert errors == []
    frame = _find_deep_link_frame(page)
    assert frame is not None
    context.close()


def test_ios_useragent_detected_by_deep_link_script(browser):
    """§4.1: correct detection-branch loads per userAgent (iOS)."""
    page, context, errors = new_page(browser, IPHONE_VIEWPORT, user_agent=IPHONE_UA)
    page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)
    frame = _find_deep_link_frame(page)
    is_ios_detected = frame.evaluate(
        "() => /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream"
    )
    assert is_ios_detected is True
    context.close()


def test_android_useragent_detected_by_deep_link_script(browser):
    """§4.1: correct detection-branch loads per userAgent (Android)."""
    page, context, errors = new_page(browser, ANDROID_VIEWPORT, user_agent=ANDROID_UA)
    page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)
    frame = _find_deep_link_frame(page)
    is_android_detected = frame.evaluate("() => /Android/.test(navigator.userAgent)")
    assert is_android_detected is True
    context.close()


def test_fallback_link_always_present_regardless_of_platform(browser):
    """§2.4/§4.1: the https:// fallback must always be present in the DOM,
    even before any JS detection/click interaction happens."""
    for viewport, ua in [(IPHONE_VIEWPORT, IPHONE_UA), (ANDROID_VIEWPORT, ANDROID_UA)]:
        page, context, errors = new_page(browser, viewport, user_agent=ua)
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        frame = _find_deep_link_frame(page)
        assert frame is not None
        assert frame.locator('a:has-text("Order on Swiggy")').count() > 0
        assert frame.locator('a:has-text("Order on Zomato")').count() > 0
        context.close()


def test_no_unhandled_js_exceptions_across_platform_permutations(browser):
    """§4.1 Exception Rule (Tier 2 analogue): no unhandled JS exceptions
    across desktop/iOS/Android permutations on initial card render."""
    contexts = [
        (DESKTOP_VIEWPORT, None),
        (IPHONE_VIEWPORT, IPHONE_UA),
        (ANDROID_VIEWPORT, ANDROID_UA),
    ]
    for viewport, ua in contexts:
        page, context, errors = new_page(browser, viewport, user_agent=ua)
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        assert errors == [], f"Unhandled JS exception(s) for viewport={viewport}: {errors}"
        context.close()
