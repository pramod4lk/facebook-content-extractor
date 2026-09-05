import httpx
import pytest

from facebook_extractor.photos.scraper import (
    derive_media_id,
    extract_image_url,
    fetch_photo_image_url,
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

    def test_unescapes_html_entities(self) -> None:
        html_page = (
            '<meta property="og:image" content="https://scontent.example.com/1.jpg?a=1&amp;b=2">'
        )
        assert extract_image_url(html_page) == "https://scontent.example.com/1.jpg?a=1&b=2"

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
