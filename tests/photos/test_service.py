import httpx
import pytest

from facebook_extractor.photos.service import PhotoExtractionError, fetch_photos
from facebook_extractor.shared.http_client import GraphAPIClient


def make_client(handler) -> GraphAPIClient:
    return GraphAPIClient(
        access_token="test-token",
        api_version="v25.0",
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _seconds: None,
    )


def test_successful_extraction_normalizes_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "1",
                        "name": "A caption",
                        "created_time": "2026-01-01T00:00:00+0000",
                        "height": 100,
                        "width": 200,
                        "link": "https://facebook.com/photo/1",
                        "source": "https://scontent.example.com/1.jpg",
                    }
                ]
            },
        )

    photos = fetch_photos(make_client(handler), "page-1")

    assert len(photos) == 1
    photo = photos[0]
    assert photo.id == "1"
    assert photo.page_id == "page-1"
    assert photo.caption == "A caption"
    assert photo.download_url == "https://scontent.example.com/1.jpg"


def test_empty_response_returns_empty_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    assert fetch_photos(make_client(handler), "page-1") == []


def test_missing_optional_fields_handled_gracefully() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "1"}]})

    photos = fetch_photos(make_client(handler), "page-1")

    assert photos[0].caption is None
    assert photos[0].download_url is None


def test_item_without_id_is_skipped_not_fatal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"name": "no id here"}, {"id": "2"}]})

    photos = fetch_photos(make_client(handler), "page-1")

    assert [p.id for p in photos] == ["2"]


def test_follows_pagination_across_pages() -> None:
    pages = [
        {
            "data": [{"id": "1"}],
            "paging": {"next": "https://graph.facebook.com/v25.0/page-1/photos?after=abc"},
        },
        {"data": [{"id": "2"}]},
    ]
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json=pages[len(calls) - 1])

    photos = fetch_photos(make_client(handler), "page-1")

    assert [p.id for p in photos] == ["1", "2"]
    assert len(calls) == 2


def test_limit_stops_before_exhausting_pagination() -> None:
    pages = [
        {
            "data": [{"id": "1"}, {"id": "2"}],
            "paging": {"next": "https://graph.facebook.com/v25.0/page-1/photos?after=abc"},
        },
        {"data": [{"id": "3"}]},
    ]
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json=pages[len(calls) - 1])

    photos = fetch_photos(make_client(handler), "page-1", limit=1)

    assert [p.id for p in photos] == ["1"]
    assert len(calls) == 1


def test_api_failure_raises_photo_extraction_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"message": "Insufficient permission"}})

    with pytest.raises(PhotoExtractionError, match="Could not retrieve Photos"):
        fetch_photos(make_client(handler), "page-1")
