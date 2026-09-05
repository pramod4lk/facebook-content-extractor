import html
import re
from urllib.parse import parse_qs, urlparse

import httpx

from facebook_extractor.shared.scraping import ScrapeError, fetch_html

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
