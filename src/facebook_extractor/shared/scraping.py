import logging
from collections.abc import Callable, Iterator

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "facebook-extractor/0.2 (unofficial page scraper; see SPEC.md)"
_LOGIN_WALL_MARKERS = ("log in to facebook", "log into facebook", "you must log in")
_MAX_LISTING_PAGES = 20


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

    text = response.text
    if any(marker in text.lower() for marker in _LOGIN_WALL_MARKERS):
        raise ScrapeError(
            f"Facebook returned a login-required page for {url}. This tool does not "
            "log in or hold a session, so this page cannot be scraped this way."
        )
    return text


def iter_listing_pages(
    client: httpx.Client,
    first_url: str,
    find_next_link: Callable[[str], str | None],
    *,
    max_pages: int = _MAX_LISTING_PAGES,
) -> Iterator[str]:
    """Yield each listing page's HTML, following `find_next_link(html) -> next_url`
    pagination links until none is found or `max_pages` is reached (a hard safety cap,
    not something Facebook enforces or documents)."""
    url = first_url
    for _ in range(max_pages):
        page_html = fetch_html(client, url)
        yield page_html
        next_url = find_next_link(page_html)
        if not next_url:
            return
        url = next_url
