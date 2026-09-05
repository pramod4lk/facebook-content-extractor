import logging
from typing import Any

from facebook_extractor.shared.http_client import GraphAPIClient, GraphAPIError

from .models import Reel

logger = logging.getLogger(__name__)

_FIELDS = "id,description,length,created_time,permalink_url,source"


class ReelExtractionError(Exception):
    """Raised when Reels cannot be retrieved for a Page (SPEC.md FR-005).

    As confirmed against the current Meta Graph API docs (v25.0), `{page-id}/video_reels`
    is publish-only (POST) and `{page-id}/videos` does not support reading either — Meta
    does not expose any endpoint to list or retrieve a Page's *existing* Reels. This call
    is therefore expected to always fail; it is made anyway (rather than short-circuited)
    so the real Meta error is surfaced, and so this starts working with no code change if
    Meta ever adds a read endpoint. The CLI MUST report this and continue with Photos
    rather than treating it as fatal to the whole run.
    """


def fetch_reels(client: GraphAPIClient, page_id: str, *, limit: int | None = None) -> list[Reel]:
    try:
        reels: list[Reel] = []
        for page in client.paginate(f"{page_id}/video_reels", {"fields": _FIELDS}):
            for raw in page.get("data", []):
                reel = _normalize(raw, page_id)
                if reel is None:
                    continue
                reels.append(reel)
                if limit is not None and len(reels) >= limit:
                    return reels
        return reels
    except GraphAPIError as exc:
        raise ReelExtractionError(
            f"Reels are not available via the Meta Graph API for Page {page_id}: {exc}\n"
            "As of Graph API v25.0, Meta does not provide a read endpoint for a Page's "
            "existing Reels (video_reels is publish-only). This is a platform limitation, "
            "not a permissions issue."
        ) from exc


def _normalize(raw: dict[str, Any], page_id: str) -> Reel | None:
    reel_id = raw.get("id")
    if not reel_id:
        logger.warning("Skipping a Reel with no 'id' field for Page %s", page_id)
        return None

    source = raw.get("source")
    return Reel(
        id=reel_id,
        page_id=page_id,
        caption=raw.get("description"),
        duration=raw.get("length"),
        created_at=raw.get("created_time"),
        permalink=raw.get("permalink_url"),
        media_url=source,
        download_url=source,
    )
