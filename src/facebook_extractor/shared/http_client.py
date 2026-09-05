import logging
import time
from collections.abc import Callable, Iterator
from typing import Any

import httpx

from .retry import MAX_ATTEMPTS, RETRYABLE_STATUS_CODES, backoff_seconds

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 30.0


class GraphAPIError(Exception):
    """A non-retryable (or retry-exhausted) Meta Graph API error (SPEC.md API-004)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GraphAPIClient:
    """Single dedicated client for all Meta Graph API communication (API-004). Handles
    auth, pagination, timeouts, retries with backoff, and rate-limit responses. Requests
    are performed sequentially — this client is not safe for concurrent use."""

    def __init__(
        self,
        access_token: str,
        api_version: str,
        *,
        base_url: str = "https://graph.facebook.com",
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._access_token = access_token
        self._api_version = api_version
        self._base_url = base_url.rstrip("/")
        self._sleep_fn = sleep_fn
        self._client = httpx.Client(timeout=timeout_seconds, transport=transport)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GraphAPIClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET a Graph API edge, e.g. get("{page-id}/photos", {"type": "uploaded"})."""
        url = f"{self._base_url}/{self._api_version}/{path.lstrip('/')}"
        request_params = {**(params or {}), "access_token": self._access_token}
        return self._request_with_retry(url, request_params, log_label=path)

    def paginate(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        """Yield each page's raw JSON payload (FR-006) until Meta reports no next page.
        Callers are responsible for stopping early once --limit is reached."""
        payload = self.get(path, params)
        yield payload
        next_url = payload.get("paging", {}).get("next")
        while next_url:
            payload = self._request_with_retry(next_url, None, log_label="(next page)")
            yield payload
            next_url = payload.get("paging", {}).get("next")

    def _request_with_retry(
        self, url: str, params: dict[str, Any] | None, *, log_label: str
    ) -> dict[str, Any]:
        last_error: Exception | None = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self._client.get(url, params=params)
            except httpx.TransportError as exc:
                last_error = exc
                logger.warning(
                    "Network error on attempt %d/%d for %s: %s",
                    attempt,
                    MAX_ATTEMPTS,
                    log_label,
                    exc,
                )
                if attempt < MAX_ATTEMPTS:
                    self._sleep_fn(backoff_seconds(attempt, None))
                continue

            if response.status_code == 200:
                return response.json()

            payload = _safe_json(response)
            if response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_ATTEMPTS:
                logger.warning(
                    "Retryable Graph API error %d on attempt %d/%d for %s",
                    response.status_code,
                    attempt,
                    MAX_ATTEMPTS,
                    log_label,
                )
                self._sleep_fn(backoff_seconds(attempt, response.headers.get("Retry-After")))
                continue

            raise GraphAPIError(
                _describe_error(response.status_code, payload), status_code=response.status_code
            )

        raise GraphAPIError(
            f"Request to {log_label} failed after {MAX_ATTEMPTS} attempts: {last_error}"
        )


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        return response.json()
    except ValueError:
        return {}


def _describe_error(status_code: int, payload: dict[str, Any]) -> str:
    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    message = error.get("message") or f"HTTP {status_code}"
    details = ", ".join(
        f"{key}={error[key]}" for key in ("type", "code") if error.get(key) is not None
    )
    return f"Meta Graph API error ({status_code}): {message}" + (f" [{details}]" if details else "")
