from dataclasses import dataclass


@dataclass(frozen=True)
class Photo:
    """A Photo discovered by scraping (SPEC.md §19) — only what's reliably extractable
    from a public page's own markup, not the richer set Graph API would offer."""

    id: str
    permalink: str
    download_url: str | None = None
