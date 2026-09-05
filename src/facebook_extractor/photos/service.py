import logging
from typing import Any

from facebook_extractor.shared.http_client import GraphAPIClient, GraphAPIError

from .models import Photo

logger = logging.getLogger(__name__)

_FIELDS = "id,name,created_time,height,width,link,source"


class PhotoExtractionError(Exception):
    """Raised when Photos cannot be retrieved for a Page at all (SPEC.md FR-004)."""


def fetch_photos(
    client: GraphAPIClient, page_id: str, *, limit: int | None = None
) -> list[Photo]:
    """Fetch a Page's uploaded Photos, following pagination (FR-006) until exhausted or
    `limit` items are collected. `limit` is this media type's own cap (CLI-004) — it is
    not shared with Reels."""
    photos: list[Photo] = []
    try:
        for page in client.paginate(f"{page_id}/photos", {"type": "uploaded", "fields": _FIELDS}):
            for raw in page.get("data", []):
                photo = _normalize(raw, page_id)
                if photo is None:
                    continue
                photos.append(photo)
                if limit is not None and len(photos) >= limit:
                    return photos
    except GraphAPIError as exc:
        raise PhotoExtractionError(f"Could not retrieve Photos for Page {page_id}: {exc}") from exc

    return photos


def _normalize(raw: dict[str, Any], page_id: str) -> Photo | None:
    photo_id = raw.get("id")
    if not photo_id:
        logger.warning("Skipping a Photo with no 'id' field for Page %s", page_id)
        return None

    source = raw.get("source")
    return Photo(
        id=photo_id,
        page_id=page_id,
        caption=raw.get("name"),
        width=raw.get("width"),
        height=raw.get("height"),
        created_at=raw.get("created_time"),
        permalink=raw.get("link"),
        media_url=source,
        download_url=source,
    )
