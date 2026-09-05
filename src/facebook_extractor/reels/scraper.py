import html
import logging
import re
from urllib.parse import parse_qs, urljoin, urlparse

import httpx

from facebook_extractor.shared.scraping import ScrapeError, fetch_html, iter_listing_pages

from .models import Reel

logger = logging.getLogger(__name__)

_BASE_URL = "https://m.facebook.com"
_REEL_LINK_PATTERN = re.compile(r'href="(/reel/\d+[^"]*)"')
_MORE_LINK_PATTERN = re.compile(r'href="([^"]*(?:videos|reels)[^"]*(?:start|cursor)=[^"]+)"', re.I)
_HD_VIDEO_PATTERN = re.compile(r'"playable_url_quality_hd":"([^"]+)"')
_SD_VIDEO_PATTERN = re.compile(r'"playable_url":"([^"]+)"')
_OG_VIDEO_PATTERN = re.compile(
    r'<meta[^>]+property="og:video(?::secure_url)?"[^>]+content="([^"]+)"'
)


def derive_media_id(url: str) -> str:
    """Best-effort numeric ID for filenames (e.g. from /reel/<id>/ or ?v=<id>); falls
    back to a hash of the URL if none is found."""
    parsed = urlparse(url)
    for part in reversed([p for p in parsed.path.split("/") if p]):
        if part.isdigit():
            return part
    query_id = parse_qs(parsed.query).get("v", [None])[0]
    if query_id and query_id.isdigit():
        return query_id
    return str(abs(hash(url)))


def extract_video_url(page_html: str) -> str:
    """Pull the direct video URL out of a public Reel/video page's own HTML — the same
    embedded data Facebook serves to any unauthenticated browser or link-preview
    crawler. Raises ScrapeError if the page looks blocked or its markup has changed."""
    for pattern in (_HD_VIDEO_PATTERN, _SD_VIDEO_PATTERN, _OG_VIDEO_PATTERN):
        match = pattern.search(page_html)
        if match:
            return html.unescape(match.group(1).replace("\\/", "/"))
    raise ScrapeError(
        "Could not find a video URL in this page. Facebook likely changed its page "
        "markup (this method is unofficial and unversioned), or this isn't a public "
        "Reel/video."
    )


def fetch_reel_video_url(client: httpx.Client, reel_url: str) -> str:
    return extract_video_url(fetch_html(client, reel_url))


def _find_more_link(page_html: str) -> str | None:
    match = _MORE_LINK_PATTERN.search(page_html)
    return urljoin(_BASE_URL, html.unescape(match.group(1))) if match else None


def list_reels(client: httpx.Client, page_slug: str, *, limit: int | None = None) -> list[Reel]:
    """Discover a Page's Reels by crawling its public mobile-site videos listing
    (SPEC.md §19). Best-effort: a broken listing/pagination fetch after the first page
    stops the crawl early rather than losing what's already been found; a single item
    whose video URL can't be resolved is skipped, not fatal."""
    listing_url = f"{_BASE_URL}/{page_slug}/videos"
    reels: list[Reel] = []
    seen_ids: set[str] = set()

    try:
        for page_html in iter_listing_pages(client, listing_url, _find_more_link):
            for match in _REEL_LINK_PATTERN.finditer(page_html):
                link = urljoin(_BASE_URL, html.unescape(match.group(1)))
                media_id = derive_media_id(link)
                if media_id in seen_ids:
                    continue
                seen_ids.add(media_id)

                try:
                    video_url = fetch_reel_video_url(client, link)
                except ScrapeError as exc:
                    logger.warning("Skipping reel %s: %s", media_id, exc)
                    continue

                reels.append(Reel(id=media_id, permalink=link, download_url=video_url))
                if limit is not None and len(reels) >= limit:
                    return reels
    except ScrapeError:
        if not reels:
            raise
        logger.warning("Stopped scanning for more Reels early after a fetch failure")

    return reels
