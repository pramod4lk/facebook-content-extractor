import httpx
import pytest

from facebook_extractor.shared.http_client import GraphAPIClient, GraphAPIError


def make_client(handler, **kwargs) -> GraphAPIClient:
    return GraphAPIClient(
        access_token="test-token",
        api_version="v25.0",
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _seconds: None,
        **kwargs,
    )


def test_successful_response_returns_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["access_token"] == "test-token"
        return httpx.Response(200, json={"data": [{"id": "1"}]})

    client = make_client(handler)

    result = client.get("123/photos")

    assert result == {"data": [{"id": "1"}]}


def test_access_token_never_appears_in_logs_even_on_retry(caplog) -> None:
    responses = iter(
        [
            httpx.Response(503, json={"error": {"message": "temporarily unavailable"}}),
            httpx.Response(200, json={"data": []}),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["access_token"] == "test-token"
        return next(responses)

    client = make_client(handler)
    with caplog.at_level("WARNING"):
        client.get("123/photos")

    assert caplog.text
    assert "test-token" not in caplog.text


def test_non_retryable_api_error_raises_immediately() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(400, json={"error": {"message": "Invalid Page ID", "code": 100}})

    client = make_client(handler)

    with pytest.raises(GraphAPIError) as exc_info:
        client.get("bad-id/photos")

    assert len(calls) == 1
    assert "Invalid Page ID" in str(exc_info.value)
    assert exc_info.value.status_code == 400


def test_authentication_error_raises_immediately() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Invalid OAuth access token"}})

    client = make_client(handler)

    with pytest.raises(GraphAPIError) as exc_info:
        client.get("123/photos")

    assert exc_info.value.status_code == 401


def test_retries_transient_5xx_then_succeeds() -> None:
    responses = iter(
        [
            httpx.Response(503, json={"error": {"message": "temporarily unavailable"}}),
            httpx.Response(200, json={"data": [{"id": "1"}]}),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return next(responses)

    client = make_client(handler)

    result = client.get("123/photos")

    assert result == {"data": [{"id": "1"}]}


def test_gives_up_after_max_attempts() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500, json={"error": {"message": "server error"}})

    client = make_client(handler)

    with pytest.raises(GraphAPIError):
        client.get("123/photos")

    assert len(calls) == 3


def test_retries_network_failure() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) < 2:
            raise httpx.ConnectError("connection reset", request=request)
        return httpx.Response(200, json={"data": []})

    client = make_client(handler)

    result = client.get("123/photos")

    assert result == {"data": []}
    assert len(calls) == 2


def test_paginate_follows_next_link_until_exhausted() -> None:
    pages = [
        {"data": [{"id": "1"}], "paging": {"next": "https://graph.facebook.com/v25.0/123/photos?after=abc"}},
        {"data": [{"id": "2"}]},
    ]
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json=pages[len(calls) - 1])

    client = make_client(handler)

    results = list(client.paginate("123/photos"))

    assert [page["data"][0]["id"] for page in results] == ["1", "2"]
    assert len(calls) == 2
