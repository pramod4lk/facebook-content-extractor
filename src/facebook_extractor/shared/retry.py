MAX_ATTEMPTS = 3
BASE_BACKOFF_SECONDS = 1.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def backoff_seconds(attempt: int, retry_after: str | None) -> float:
    """Exponential backoff (1s, 2s, 4s, ...), honoring a numeric `Retry-After` header
    when Meta/the CDN provides one (SPEC.md §10 Retry Requirements)."""
    delay = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
    if retry_after:
        try:
            delay = max(delay, float(retry_after))
        except ValueError:
            pass
    return delay
