import logging

from facebook_extractor.shared.http_client import GraphAPIClient, GraphAPIError

from .models import Page

logger = logging.getLogger(__name__)


class PageResolutionError(Exception):
    """Raised when a Facebook Page URL cannot be resolved to a Page identity (SPEC.md
    FR-003) — e.g. the Page doesn't exist, or the configured credentials lack access."""


def resolve_page(client: GraphAPIClient, page_slug: str) -> Page:
    """Resolve a Page's slug/ID (from shared.url_parser.ParsedPageUrl.page_slug) to its
    Page identity via the Graph API."""
    try:
        payload = client.get(page_slug, {"fields": "id,name,username"})
    except GraphAPIError as exc:
        raise PageResolutionError(f"Could not resolve Facebook Page '{page_slug}': {exc}") from exc

    page_id = payload.get("id")
    if not page_id:
        raise PageResolutionError(
            f"Meta's API response for '{page_slug}' did not include a Page ID."
        )

    logger.info("Resolved Page '%s' to id=%s", page_slug, page_id)
    return Page(id=page_id, name=payload.get("name", page_slug), username=payload.get("username"))
