from dataclasses import dataclass


@dataclass(frozen=True)
class Reel:
    """SPEC.md §9 Data Models. As of Graph API v25.0 there is no read endpoint for a
    Page's existing Reels (see reels.service), so nothing currently produces this —
    it exists so the code is ready the day Meta adds one."""

    id: str
    page_id: str
    caption: str | None = None
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    created_at: str | None = None
    permalink: str | None = None
    media_url: str | None = None
    download_url: str | None = None
