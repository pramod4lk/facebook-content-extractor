import sqlite3
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS downloads (
    media_type TEXT NOT NULL,
    media_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    local_filename TEXT,
    download_status TEXT NOT NULL,
    downloaded_at TEXT,
    PRIMARY KEY (media_type, media_id)
);
"""


class DownloadStatus(StrEnum):
    PENDING = "pending"
    DOWNLOADED = "downloaded"
    FAILED = "failed"
    SKIPPED = "skipped"


class Manifest:
    """SQLite-backed download manifest (SPEC.md FR-013). One row per (media_type,
    media_id); used for duplicate detection and resuming across runs (FR-014). No
    page scoping — a run processes an arbitrary batch of URLs, not one Page."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(db_path)
        self._connection.execute(_SCHEMA)
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "Manifest":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def get_status(self, *, media_type: str, media_id: str) -> DownloadStatus | None:
        row = self._connection.execute(
            "SELECT download_status FROM downloads WHERE media_type = ? AND media_id = ?",
            (media_type, media_id),
        ).fetchone()
        return DownloadStatus(row[0]) if row else None

    def record(
        self,
        *,
        media_type: str,
        media_id: str,
        source_url: str,
        status: DownloadStatus,
        local_filename: str | None = None,
    ) -> None:
        is_downloaded = status == DownloadStatus.DOWNLOADED
        downloaded_at = datetime.now(UTC).isoformat() if is_downloaded else None
        values = (media_type, media_id, source_url, local_filename, status.value, downloaded_at)
        self._connection.execute(
            """
            INSERT INTO downloads
                (media_type, media_id, source_url, local_filename,
                 download_status, downloaded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(media_type, media_id) DO UPDATE SET
                source_url = excluded.source_url,
                local_filename = excluded.local_filename,
                download_status = excluded.download_status,
                downloaded_at = excluded.downloaded_at
            """,
            values,
        )
        self._connection.commit()


def should_skip(existing_status: DownloadStatus | None, *, force: bool) -> bool:
    """FR-011/FR-014: previously-downloaded media is skipped by default; --force
    re-downloads it. Previously-failed media is always retried (never skipped)."""
    if force:
        return False
    return existing_status == DownloadStatus.DOWNLOADED
