import httpx
import pytest

from facebook_extractor.reels.scraper import (
    derive_media_id,
    extract_video_url,
    fetch_reel_video_url,
)
from facebook_extractor.shared.scraping import ScrapeError


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


class TestDeriveMediaId:
    def test_extracts_id_from_reel_path(self) -> None:
        assert derive_media_id("https://m.facebook.com/reel/1234567890/") == "1234567890"

    def test_extracts_id_from_query_param(self) -> None:
        assert derive_media_id("https://m.facebook.com/watch/?v=987654321") == "987654321"

    def test_falls_back_to_hash_when_no_id_found(self) -> None:
        result = derive_media_id("https://m.facebook.com/somepage/videos/no-numbers-here")
        assert result.isdigit()


class TestExtractVideoUrl:
    def test_extracts_hd_playable_url(self) -> None:
        html_page = (
            '<script>{"playable_url_quality_hd":"https:\\/\\/video.example.com\\/1.mp4"}</script>'
        )
        assert extract_video_url(html_page) == "https://video.example.com/1.mp4"

    def test_falls_back_to_sd_playable_url(self) -> None:
        html_page = '<script>{"playable_url":"https:\\/\\/video.example.com\\/2.mp4"}</script>'
        assert extract_video_url(html_page) == "https://video.example.com/2.mp4"

    def test_falls_back_to_og_video_meta_tag(self) -> None:
        html_page = (
            '<meta property="og:video:secure_url" content="https://video.example.com/3.mp4">'
        )
        assert extract_video_url(html_page) == "https://video.example.com/3.mp4"

    def test_raises_clear_error_when_pattern_not_found(self) -> None:
        with pytest.raises(ScrapeError, match="Could not find a video URL"):
            extract_video_url("<html><body>nothing relevant here</body></html>")


class TestFetchReelVideoUrl:
    def test_successful_fetch_extracts_url(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, text='<meta property="og:video" content="https://video.example.com/1.mp4">'
            )

        url = fetch_reel_video_url(make_client(handler), "https://m.facebook.com/reel/1/")
        assert url == "https://video.example.com/1.mp4"

    def test_login_wall_raises_clear_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<title>Log into Facebook</title>")

        with pytest.raises(ScrapeError, match="login-required"):
            fetch_reel_video_url(make_client(handler), "https://m.facebook.com/reel/1/")
