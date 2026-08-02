"""Deep-link redirection per spec §2.4 (mobile-first, cross-platform).

Renders a small JS snippet per card that:
  - attempts the native custom-scheme deep link
  - always keeps the https:// fallback link present in the DOM
  - branches by platform: Android uses a ~1.5s visibilitychange timer;
    iOS uses a longer ~2.5s timer (Universal Links assumed unregistered
    per §6 gap #3 - finalized) instead of visibilitychange detection.
"""
import html

ANDROID_TIMEOUT_MS = 1500
IOS_TIMEOUT_MS = 2500


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def render_deep_link_snippet(
    restaurant_id: str,
    swiggy_url: str,
    zomato_url: str,
    swiggy_scheme: str | None = None,
    zomato_scheme: str | None = None,
    container_id_suffix: str = "",
) -> str:
    """Returns an HTML fragment (for st.components.v1.html) with Swiggy/Zomato
    deep-link buttons implementing the §2.4 platform-branching behavior.

    The plain https:// fallback links are always present in the DOM
    (as real <a> tags) regardless of JS detection outcome, per spec.
    """
    swiggy_scheme = swiggy_scheme or f"swiggy://menu/{restaurant_id}"
    zomato_scheme = zomato_scheme or f"zomato://restaurant/{restaurant_id}"
    uid = f"cravecare-deeplink-{_escape(restaurant_id)}{container_id_suffix}"

    return f"""
<div id="{uid}">
  <a id="{uid}-swiggy-fallback" href="{_escape(swiggy_url)}" target="_blank" rel="noopener"
     style="display:inline-block;padding:8px 16px;margin-right:8px;background:#fc8019;color:white;
            border-radius:6px;text-decoration:none;font-family:sans-serif;">Order on Swiggy</a>
  <a id="{uid}-zomato-fallback" href="{_escape(zomato_url)}" target="_blank" rel="noopener"
     style="display:inline-block;padding:8px 16px;background:#e23744;color:white;
            border-radius:6px;text-decoration:none;font-family:sans-serif;">Order on Zomato</a>
</div>
<script>
(function() {{
  function isIOS() {{
    return /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  }}
  function isAndroid() {{
    return /Android/.test(navigator.userAgent);
  }}

  function attemptDeepLink(nativeUrl, fallbackUrl, timeoutMs) {{
    var didHide = false;
    function onVisibilityChange() {{
      if (document.hidden) {{
        didHide = true;
      }}
    }}
    document.addEventListener('visibilitychange', onVisibilityChange);

    // Primary attempt: custom scheme.
    window.location.href = nativeUrl;

    setTimeout(function() {{
      document.removeEventListener('visibilitychange', onVisibilityChange);
      if (!didHide) {{
        // App didn't open (or, on iOS, detection is unreliable) -> fallback.
        window.location.href = fallbackUrl;
      }}
    }}, timeoutMs);
  }}

  function wireCard(linkEl, nativeUrl) {{
    if (!linkEl) return;
    linkEl.addEventListener('click', function(e) {{
      e.preventDefault();
      var fallbackUrl = linkEl.getAttribute('href');
      if (isAndroid()) {{
        attemptDeepLink(nativeUrl, fallbackUrl, {ANDROID_TIMEOUT_MS});
      }} else if (isIOS()) {{
        // Universal Links assumed unregistered (spec §6 gap #3, resolved):
        // use the longer timer fallback instead of visibilitychange.
        attemptDeepLink(nativeUrl, fallbackUrl, {IOS_TIMEOUT_MS});
      }} else {{
        // Desktop/unknown UA: go straight to the guaranteed web fallback.
        window.location.href = fallbackUrl;
      }}
    }});
  }}

  wireCard(document.getElementById("{uid}-swiggy-fallback"), "{_escape(swiggy_scheme)}");
  wireCard(document.getElementById("{uid}-zomato-fallback"), "{_escape(zomato_scheme)}");
}})();
</script>
"""


def swiggy_web_url(restaurant_id: str) -> str:
    return f"https://www.swiggy.com/restaurants/{restaurant_id}"


def zomato_web_url(restaurant_id: str) -> str:
    return f"https://www.zomato.com/mumbai/{restaurant_id}"
