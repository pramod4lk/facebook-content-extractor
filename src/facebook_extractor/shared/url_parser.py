from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

_VALID_HOSTS = {"facebook.com", "www.facebook.com", "m.facebook.com"}


class InvalidFacebookUrlError(Exception):
    """Raised when a configured Facebook Page URL cannot be parsed (SPEC.md FR-002)."""


@dataclass(frozen=True)
class ParsedPageUrl:
    normalized_url: str
    page_slug: str
    """The Page's vanity username (e.g. "examplepage"), or its numeric ID for
    profile.php?id=... style URLs."""


def parse_page_url(raw_url: str) -> ParsedPageUrl:
    """Validate and normalize a Facebook Page URL (FR-002). Query parameters that don't
    affect Page identification (tracking params, ref=, etc.) are dropped."""
    parsed = urlparse(raw_url.strip())

    if parsed.scheme not in ("http", "https") or parsed.netloc.lower() not in _VALID_HOSTS:
        raise InvalidFacebookUrlError(f"'{raw_url}' is not a valid Facebook Page URL.")

    path = parsed.path.strip("/")
    if not path:
        raise InvalidFacebookUrlError(f"'{raw_url}' does not contain a Facebook Page identifier.")

    slug = path.split("/")[0]

    if slug == "profile.php":
        page_id = parse_qs(parsed.query).get("id", [None])[0]
        if not page_id:
            raise InvalidFacebookUrlError(
                f"'{raw_url}' is a profile.php URL but is missing the 'id' query parameter."
            )
        return ParsedPageUrl(
            normalized_url=f"https://www.facebook.com/profile.php?id={page_id}",
            page_slug=page_id,
        )

    return ParsedPageUrl(
        normalized_url=f"https://www.facebook.com/{slug}",
        page_slug=slug,
    )
