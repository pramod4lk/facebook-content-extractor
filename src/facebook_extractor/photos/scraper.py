import html
import logging
import re
from urllib.parse import parse_qs, urljoin, urlparse

import httpx

from facebook_extractor.shared.scraping import ScrapeError, fetch_html, iter_listing_pages

from .models import Photo

logger = logging.getLogger(__name__)

_BASE_URL = "https://m.facebook.com"
_PHOTO_LINK_PATTERN = re.compile(r'href="(/photo(?:\.php)?/?\?fbid=\d+[^"]*)"')
_MORE_LINK_PATTERN = re.compile(r'href="([^"]*photos[^"]*(?:start|cursor)=[^"]+)"', re.I)
_OG_IMAGE_PATTERN = re.compile(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"')


def derive_media_id(url: str) -> str:
    """The `fbid` query param uniquely identifies a Photo; falls back to a hash."""
    fbid = parse_qs(urlparse(url).query).get("fbid", [None])[0]
    if fbid and fbid.isdigit():
        return fbid
    return str(abs(hash(url)))


def extract_image_url(page_html: str) -> str:
    """Pull the direct image URL out of a public Photo permalink page's own HTML —
    the same og:image data Facebook serves to any unauthenticated browser or
    link-preview crawler. Raises ScrapeError if the markup doesn't match."""
    match = _OG_IMAGE_PATTERN.search(page_html)
    if not match:
        raise ScrapeError(
            "Could not find an image URL in this page. Facebook likely changed its "
            "page markup (this method is unofficial and unversioned), or this isn't "
            "a public Photo."
        )
    return html.unescape(match.group(1).replace("\\/", "/"))


def fetch_photo_image_url(client: httpx.Client, photo_url: str) -> str:
    return extract_image_url(fetch_html(client, photo_url))


def _find_more_link(page_html: str) -> str | None:
    match = _MORE_LINK_PATTERN.search(page_html)
    return urljoin(_BASE_URL, html.unescape(match.group(1))) if match else None


def list_photos(client: httpx.Client, page_slug: str, *, limit: int | None = None) -> list[Photo]:
    """Discover a Page's Photos by crawling its public mobile-site photos listing
    (SPEC.md §19). Best-effort: a broken listing/pagination fetch after the first page
    stops the crawl early rather than losing what's already been found; a single item
    whose image URL can't be resolved is skipped, not fatal."""
    listing_url = f"{_BASE_URL}/{page_slug}/photos"
    photos: list[Photo] = []
    seen_ids: set[str] = set()

    try:
        for page_html in iter_listing_pages(client, listing_url, _find_more_link):
            for match in _PHOTO_LINK_PATTERN.finditer(page_html):
                link = urljoin(_BASE_URL, html.unescape(match.group(1)))
                media_id = derive_media_id(link)
                if media_id in seen_ids:
                    continue
                seen_ids.add(media_id)

                try:
                    image_url = fetch_photo_image_url(client, link)
                except ScrapeError as exc:
                    logger.warning("Skipping photo %s: %s", media_id, exc)
                    continue

                photos.append(Photo(id=media_id, permalink=link, download_url=image_url))
                if limit is not None and len(photos) >= limit:
                    return photos
    except ScrapeError:
        if not photos:
            raise
        logger.warning("Stopped scanning for more Photos early after a fetch failure")

    return photos
