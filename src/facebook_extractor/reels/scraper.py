import html
import re
from urllib.parse import parse_qs, urlparse

import httpx

from facebook_extractor.shared.scraping import ScrapeError, fetch_html

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
    """Attempt to pull a direct video URL out of a Reel/video page's own HTML. Kept as a
    real, live attempt (not a hardcoded failure) so this self-heals if Facebook ever
    serves this data server-rendered again — but as of this version it's confirmed NOT
    to, on every URL shape tried (SPEC.md §9 SCRAPE-006): desktop `www.facebook.com`
    permalinks return 200 with no video data at all (loaded by JavaScript after page
    load, which this tool deliberately doesn't run), and every mobile path
    (`m.facebook.com`, `mbasic.facebook.com`) redirects to a login wall instead. This is
    expected to keep failing, not a bug to chase with more patterns."""
    for pattern in (_HD_VIDEO_PATTERN, _SD_VIDEO_PATTERN, _OG_VIDEO_PATTERN):
        match = pattern.search(page_html)
        if match:
            return html.unescape(match.group(1).replace("\\/", "/"))
    raise ScrapeError(
        "Could not find a video URL in this page. As of this version, Facebook does not "
        "serve Reel/video URLs in a plain HTTP response on any URL shape tested: desktop "
        "pages load the video via JavaScript after the page loads (which this tool does "
        "not execute), and mobile pages require login. This is a confirmed platform "
        "limitation, not a bug — see SPEC.md §9 SCRAPE-006."
    )


def fetch_reel_video_url(client: httpx.Client, reel_url: str) -> str:
    return extract_video_url(fetch_html(client, reel_url))
