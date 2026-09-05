import httpx
import pytest

from facebook_extractor.photos.scraper import (
    derive_media_id,
    extract_image_url,
    fetch_photo_image_url,
    list_photos,
)
from facebook_extractor.shared.scraping import ScrapeError


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


class TestDeriveMediaId:
    def test_extracts_fbid_from_query_param(self) -> None:
        url = "https://m.facebook.com/photo/?fbid=1234567890"
        assert derive_media_id(url) == "1234567890"

    def test_falls_back_to_hash_when_no_fbid(self) -> None:
        result = derive_media_id("https://m.facebook.com/photo/?nope=1")
        assert result.isdigit()


class TestExtractImageUrl:
    def test_extracts_og_image(self) -> None:
        html_page = '<meta property="og:image" content="https://scontent.example.com/1.jpg">'
        assert extract_image_url(html_page) == "https://scontent.example.com/1.jpg"

    def test_raises_clear_error_when_pattern_not_found(self) -> None:
        with pytest.raises(ScrapeError, match="Could not find an image URL"):
            extract_image_url("<html><body>nothing relevant here</body></html>")


class TestFetchPhotoImageUrl:
    def test_successful_fetch_extracts_url(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, text='<meta property="og:image" content="https://scontent.example.com/1.jpg">'
            )

        url = fetch_photo_image_url(make_client(handler), "https://m.facebook.com/photo/?fbid=1")
        assert url == "https://scontent.example.com/1.jpg"

    def test_login_wall_raises_clear_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<title>Log into Facebook</title>")

        with pytest.raises(ScrapeError, match="login-required"):
            fetch_photo_image_url(make_client(handler), "https://m.facebook.com/photo/?fbid=1")


class TestListPhotos:
    def test_discovers_and_resolves_photos(self) -> None:
        listing_html = (
            '<a href="/photo/?fbid=111">a</a> <a href="/photo.php?fbid=222">b</a>'
        )

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/examplepage/photos":
                return httpx.Response(200, text=listing_html)
            image_url = f"https://x.com{request.url.path}.jpg"
            return httpx.Response(200, text=f'<meta property="og:image" content="{image_url}">')

        photos = list_photos(make_client(handler), "examplepage")

        assert {p.id for p in photos} == {"111", "222"}

    def test_respects_limit(self) -> None:
        listing_html = '<a href="/photo/?fbid=111">a</a> <a href="/photo/?fbid=222">b</a>'

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/examplepage/photos":
                return httpx.Response(200, text=listing_html)
            return httpx.Response(200, text='<meta property="og:image" content="https://x.com/i.jpg">')

        photos = list_photos(make_client(handler), "examplepage", limit=1)

        assert len(photos) == 1

    def test_deduplicates_repeated_links(self) -> None:
        listing_html = '<a href="/photo/?fbid=111">a</a> <a href="/photo/?fbid=111">again</a>'

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/examplepage/photos":
                return httpx.Response(200, text=listing_html)
            return httpx.Response(200, text='<meta property="og:image" content="https://x.com/111.jpg">')

        photos = list_photos(make_client(handler), "examplepage")

        assert len(photos) == 1

    def test_item_resolution_failure_is_skipped_not_fatal(self) -> None:
        listing_html = '<a href="/photo/?fbid=111">a</a> <a href="/photo/?fbid=222">b</a>'

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/examplepage/photos":
                return httpx.Response(200, text=listing_html)
            if "fbid=111" in str(request.url) or request.url.params.get("fbid") == "111":
                return httpx.Response(200, text="<html>nothing here</html>")
            return httpx.Response(200, text='<meta property="og:image" content="https://x.com/222.jpg">')

        photos = list_photos(make_client(handler), "examplepage")

        assert [p.id for p in photos] == ["222"]

    def test_initial_listing_failure_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        with pytest.raises(ScrapeError):
            list_photos(make_client(handler), "examplepage")

    def test_empty_listing_returns_empty_list(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>no photos here</html>")

        assert list_photos(make_client(handler), "examplepage") == []
