import httpx
import pytest

from facebook_extractor.page_resolution.service import PageResolutionError, resolve_page
from facebook_extractor.shared.http_client import GraphAPIClient


def make_client(handler) -> GraphAPIClient:
    return GraphAPIClient(
        access_token="test-token",
        api_version="v25.0",
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _seconds: None,
    )


def test_successful_resolution_returns_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/v25.0/examplepage")
        return httpx.Response(
            200, json={"id": "123456789", "name": "Example Page", "username": "examplepage"}
        )

    page = resolve_page(make_client(handler), "examplepage")

    assert page.id == "123456789"
    assert page.name == "Example Page"
    assert page.username == "examplepage"


def test_page_not_found_raises_resolution_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404, json={"error": {"message": "Unsupported get request.", "code": 100}}
        )

    with pytest.raises(PageResolutionError, match="Could not resolve"):
        resolve_page(make_client(handler), "does-not-exist")


def test_api_permission_failure_raises_resolution_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403, json={"error": {"message": "Insufficient permission", "code": 200}}
        )

    with pytest.raises(PageResolutionError, match="Could not resolve"):
        resolve_page(make_client(handler), "examplepage")
