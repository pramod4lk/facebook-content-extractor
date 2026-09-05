import logging
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import httpx

from .retry import MAX_ATTEMPTS, RETRYABLE_STATUS_CODES, backoff_seconds

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 30.0
_MAX_FILENAME_LENGTH = 200
_STREAM_CHUNK_SIZE = 64 * 1024

_DEFAULT_EXTENSIONS = {"photo": ".jpg", "reel": ".mp4"}
_CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
}


class DownloadError(Exception):
    """A single media item failed to download (SPEC.md §10/§12). Callers MUST catch
    this per item and continue with the rest of the batch, not abort the whole run."""


def sanitize_path_component(value: str, *, fallback: str) -> str:
    """Make `value` safe as a single filesystem path segment (FR-010): strip path
    separators/traversal characters and invalid filesystem characters, and cap length."""
    value = value.strip().replace("/", "_").replace("\\", "_")
    value = re.sub(r'[<>:"|?*\x00-\x1f]', "_", value)
    value = value.strip(". ")
    if value in ("", ".", ".."):
        value = fallback
    return value[:_MAX_FILENAME_LENGTH]


def build_filename(
    media_id: str,
    *,
    content_type: str | None,
    source_url: str | None,
    media_kind: Literal["photo", "reel"],
) -> str:
    """FR-009: `<media_id>.<extension>`. Extension is derived in order: the response's
    Content-Type header, then the source URL's own extension, then a type default."""
    safe_id = sanitize_path_component(media_id, fallback="media")
    extension = (
        _extension_from_content_type(content_type)
        or _extension_from_url(source_url)
        or _DEFAULT_EXTENSIONS[media_kind]
    )
    return f"{safe_id}{extension}"


def _extension_from_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    main_type = content_type.split(";")[0].strip().lower()
    return _CONTENT_TYPE_EXTENSIONS.get(main_type)


def _extension_from_url(source_url: str | None) -> str | None:
    if not source_url:
        return None
    suffix = Path(httpx.URL(source_url).path).suffix
    if suffix and re.fullmatch(r"\.[A-Za-z0-9]{1,5}", suffix):
        return suffix.lower()
    return None


def download_media(
    client: httpx.Client,
    source_url: str,
    destination_dir: Path,
    *,
    media_id: str,
    media_kind: Literal["photo", "reel"],
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Path:
    """Stream one media item into `destination_dir` (created automatically), one
    attempt at a time (sequential, §10/§12). Writes to a temp file and renames on
    success so a failed/interrupted download never leaves a corrupt final file."""
    if not source_url.lower().startswith("https://"):
        raise DownloadError(f"Refusing to download from a non-HTTPS URL: {source_url}")

    destination_dir.mkdir(parents=True, exist_ok=True)
    safe_id = sanitize_path_component(media_id, fallback="media")
    temp_path = destination_dir / f".{safe_id}.part"

    for attempt in range(1, MAX_ATTEMPTS + 1):
        is_last_attempt = attempt == MAX_ATTEMPTS
        try:
            with client.stream("GET", source_url, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
                if response.status_code != 200:
                    if response.status_code in RETRYABLE_STATUS_CODES and not is_last_attempt:
                        logger.warning(
                            "Retryable HTTP %d downloading %s (attempt %d/%d)",
                            response.status_code,
                            media_id,
                            attempt,
                            MAX_ATTEMPTS,
                        )
                        sleep_fn(backoff_seconds(attempt, response.headers.get("Retry-After")))
                        continue
                    raise DownloadError(f"HTTP {response.status_code} downloading media {media_id}")

                filename = build_filename(
                    media_id,
                    content_type=response.headers.get("Content-Type"),
                    source_url=source_url,
                    media_kind=media_kind,
                )
                final_path = destination_dir / filename
                with open(temp_path, "wb") as handle:
                    for chunk in response.iter_bytes(chunk_size=_STREAM_CHUNK_SIZE):
                        handle.write(chunk)

            temp_path.replace(final_path)
            return final_path

        except httpx.TransportError as exc:
            temp_path.unlink(missing_ok=True)
            if is_last_attempt:
                raise DownloadError(f"Network error downloading media {media_id}: {exc}") from exc
            logger.warning(
                "Network error downloading %s (attempt %d/%d): %s",
                media_id,
                attempt,
                MAX_ATTEMPTS,
                exc,
            )
            sleep_fn(backoff_seconds(attempt, None))
        except OSError as exc:
            temp_path.unlink(missing_ok=True)
            raise DownloadError(f"Filesystem error downloading media {media_id}: {exc}") from exc

    raise DownloadError(f"Failed to download media {media_id} after {MAX_ATTEMPTS} attempts")
