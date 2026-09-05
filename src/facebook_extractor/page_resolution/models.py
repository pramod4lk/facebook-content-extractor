from dataclasses import dataclass


@dataclass(frozen=True)
class Page:
    """A resolved Facebook Page identity (SPEC.md §9 Data Models). Only fields the API
    actually returned are populated — `username` is absent for Pages without a vanity URL."""

    id: str
    name: str
    username: str | None = None
