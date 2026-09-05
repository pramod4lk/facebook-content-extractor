import httpx
import pytest

from facebook_extractor.reels.service import ReelExtractionError, fetch_reels
from facebook_extractor.shared.http_client import GraphAPIClient


def make_client(handler) -> GraphAPIClient:
    return GraphAPIClient(
        access_token="test-token",
        api_version="v25.0",
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _seconds: None,
    )


def test_current_api_limitation_is_reported_clearly() -> None:
    """As of Graph API v25.0 this edge is publish-only; Meta returns an error for GET.
    This is the behavior real users will hit until Meta ships a read endpoint."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"error": {"message": "Unsupported get request.", "code": 100}}
        )

    with pytest.raises(ReelExtractionError, match="not available via the Meta Graph API"):
        fetch_reels(make_client(handler), "page-1")


def test_normalizes_fields_if_meta_ever_supports_reading() -> None:
    """Forward-compatibility test: if Meta ships a read endpoint, normalization must
    already work correctly without further code changes."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "1",
                        "description": "A reel",
                        "length": 12.5,
                        "created_time": "2026-01-01T00:00:00+0000",
                        "permalink_url": "https://facebook.com/reel/1",
                        "source": "https://scontent.example.com/1.mp4",
                    }
                ]
            },
        )

    reels = fetch_reels(make_client(handler), "page-1")

    assert len(reels) == 1
    assert reels[0].id == "1"
    assert reels[0].duration == 12.5
    assert reels[0].download_url == "https://scontent.example.com/1.mp4"


def test_empty_response_returns_empty_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    assert fetch_reels(make_client(handler), "page-1") == []


def test_item_without_id_is_skipped_not_fatal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"description": "no id"}, {"id": "2"}]})

    reels = fetch_reels(make_client(handler), "page-1")

    assert [r.id for r in reels] == ["2"]


def test_follows_pagination_across_pages() -> None:
    pages = [
        {
            "data": [{"id": "1"}],
            "paging": {"next": "https://graph.facebook.com/v25.0/page-1/video_reels?after=abc"},
        },
        {"data": [{"id": "2"}]},
    ]
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json=pages[len(calls) - 1])

    reels = fetch_reels(make_client(handler), "page-1")

    assert [r.id for r in reels] == ["1", "2"]
    assert len(calls) == 2
