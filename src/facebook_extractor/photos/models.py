from dataclasses import dataclass


@dataclass(frozen=True)
class Photo:
    """SPEC.md §9 Data Models — all fields but `id`/`page_id` are optional since the
    Graph API does not guarantee any of them are present (FR-004)."""

    id: str
    page_id: str
    caption: str | None = None
    width: int | None = None
    height: int | None = None
    created_at: str | None = None
    permalink: str | None = None
    media_url: str | None = None
    download_url: str | None = None
