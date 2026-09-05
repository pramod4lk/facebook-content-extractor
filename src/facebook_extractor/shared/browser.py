import logging

from playwright.sync_api import BrowserContext, Playwright, Response, sync_playwright

logger = logging.getLogger(__name__)

PROFILE_DIR = ".browser_profile"
"""Persistent browser profile (cookies, login session) stored on the user's own disk —
gitignored, never sent anywhere but Facebook. This tool never sees or stores a password;
the user logs in themselves in a real, visible browser window (see ensure_logged_in)."""

_NAVIGATION_TIMEOUT_MS = 30_000
_SETTLE_TIMEOUT_MS = 3_000
_MEDIA_CONTENT_TYPE_PREFIXES = ("video/", "image/")
_MEDIA_HOST_HINTS = ("fbcdn.net", "scontent")


class BrowserResolutionError(Exception):
    """SPEC.md §19: resolving a media URL via real browser rendering failed. Never
    auto-retried, and never escalated to CAPTCHA-solving — a checkpoint/CAPTCHA must be
    resolved by the user in the visible browser window, then the run repeated."""


def is_media_response(content_type: str, url: str) -> bool:
    """The predicate used to pick out the page's own media request from everything
    else it loads (JS bundles, tracking pixels, stylesheets, ...). Pure and unit-tested
    on its own, since the surrounding Playwright plumbing isn't (see tests)."""
    return any(content_type.startswith(p) for p in _MEDIA_CONTENT_TYPE_PREFIXES) and any(
        hint in url for hint in _MEDIA_HOST_HINTS
    )


def launch_context(playwright: Playwright, *, headless: bool) -> BrowserContext:
    return playwright.chromium.launch_persistent_context(
        PROFILE_DIR, headless=headless, viewport={"width": 1280, "height": 800}
    )


def ensure_logged_in(context: BrowserContext) -> None:
    """First run (or an expired session): open Facebook, and if it doesn't look like a
    logged-in session, pause for the user to log in manually in the visible window."""
    page = context.new_page()
    try:
        page.goto("https://www.facebook.com/", timeout=_NAVIGATION_TIMEOUT_MS)
        if "login" in page.url or "checkpoint" in page.url:
            print(
                "\nA browser window has opened. Please log into Facebook there, then "
                "press Enter here to continue.\n"
            )
            input()
    finally:
        page.close()


def resolve_media_url(context: BrowserContext, url: str) -> str:
    """Navigate to `url` in a real browser and capture the media response the page
    itself requests while rendering — this observes what Facebook's own JavaScript
    resolves, rather than reverse-engineering its internal API contract."""
    page = context.new_page()
    captured: list[str] = []

    def on_response(response: Response) -> None:
        if is_media_response(response.headers.get("content-type", ""), response.url):
            captured.append(response.url)

    page.on("response", on_response)
    try:
        page.goto(url, timeout=_NAVIGATION_TIMEOUT_MS)
        page.wait_for_timeout(_SETTLE_TIMEOUT_MS)
    except Exception as exc:
        raise BrowserResolutionError(f"Could not load {url} in the browser: {exc}") from exc
    finally:
        page.close()

    if not captured:
        raise BrowserResolutionError(
            f"No media response observed while rendering {url}. This may mean Facebook "
            "showed a checkpoint/CAPTCHA (resolve it manually in the browser window and "
            "re-run), the page changed, or this isn't a public Photo/Reel."
        )
    return captured[-1]


class LazyBrowser:
    """Launches the browser only on first actual use (i.e. only if the cheap plain-HTTP
    path fails for at least one URL) — if Facebook ever serves data without JS again,
    no browser is ever opened."""

    def __init__(self, *, headless: bool = False) -> None:
        self._headless = headless
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None

    def context(self) -> BrowserContext:
        if self._context is None:
            self._playwright = sync_playwright().start()
            self._context = launch_context(self._playwright, headless=self._headless)
            ensure_logged_in(self._context)
        return self._context

    def close(self) -> None:
        if self._context is not None:
            self._context.close()
        if self._playwright is not None:
            self._playwright.stop()
