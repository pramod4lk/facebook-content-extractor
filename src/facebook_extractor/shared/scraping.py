import httpx

USER_AGENT = "facebook-extractor/0.3 (unofficial page scraper; see SPEC.md)"
_LOGIN_WALL_MARKERS = ("log in to facebook", "log into facebook", "you must log in")


class ScrapeError(Exception):
    """SPEC.md §19: scraping a public Facebook page failed, or its markup didn't match
    what this tool expects. This is expected to happen — Facebook's page structure is
    unversioned and can change at any time. Never retried indefinitely, and never
    escalated to login, cookies, or browser automation to push through a failure."""


def fetch_html(client: httpx.Client, url: str) -> str:
    """Plain GET of a public page — no login, no cookies/session, no JS execution."""
    response = client.get(
        url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30.0
    )
    if response.status_code != 200:
        raise ScrapeError(f"HTTP {response.status_code} fetching {url}")

    if "/login" in response.url.path:
        raise ScrapeError(
            f"Facebook redirected {url} to a login page ({response.url}). This tool "
            "does not log in or hold a session, so this page cannot be scraped this way."
        )

    text = response.text
    if any(marker in text.lower() for marker in _LOGIN_WALL_MARKERS):
        raise ScrapeError(
            f"Facebook returned a login-required page for {url}. This tool does not "
            "log in or hold a session, so this page cannot be scraped this way."
        )
    return text
