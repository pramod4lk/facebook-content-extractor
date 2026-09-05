import httpx
import pytest

from facebook_extractor.reels.scraper import (
    derive_media_id,
    extract_video_url,
    fetch_reel_video_url,
    list_reels,
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


class TestListReels:
    def test_discovers_and_resolves_reels(self) -> None:
        listing_html = '<a href="/reel/111/">a</a> <a href="/reel/222/">b</a>'

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/examplepage/videos":
                return httpx.Response(200, text=listing_html)
            video_url = f"https://x.com{request.url.path}.mp4"
            return httpx.Response(200, text=f'<meta property="og:video" content="{video_url}">')

        reels = list_reels(make_client(handler), "examplepage")

        assert {r.id for r in reels} == {"111", "222"}

    def test_respects_limit(self) -> None:
        listing_html = '<a href="/reel/111/">a</a> <a href="/reel/222/">b</a>'

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/examplepage/videos":
                return httpx.Response(200, text=listing_html)
            return httpx.Response(200, text='<meta property="og:video" content="https://x.com/v.mp4">')

        reels = list_reels(make_client(handler), "examplepage", limit=1)

        assert len(reels) == 1

    def test_deduplicates_repeated_links(self) -> None:
        listing_html = '<a href="/reel/111/">a</a> <a href="/reel/111/">a again</a>'

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/examplepage/videos":
                return httpx.Response(200, text=listing_html)
            return httpx.Response(200, text='<meta property="og:video" content="https://x.com/111.mp4">')

        reels = list_reels(make_client(handler), "examplepage")

        assert len(reels) == 1

    def test_item_resolution_failure_is_skipped_not_fatal(self) -> None:
        listing_html = '<a href="/reel/111/">a</a> <a href="/reel/222/">b</a>'

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/examplepage/videos":
                return httpx.Response(200, text=listing_html)
            if request.url.path == "/reel/111/":
                return httpx.Response(200, text="<html>nothing here</html>")
            return httpx.Response(200, text='<meta property="og:video" content="https://x.com/222.mp4">')

        reels = list_reels(make_client(handler), "examplepage")

        assert [r.id for r in reels] == ["222"]

    def test_initial_listing_failure_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        with pytest.raises(ScrapeError):
            list_reels(make_client(handler), "examplepage")

    def test_empty_listing_returns_empty_list(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>no reels here</html>")

        assert list_reels(make_client(handler), "examplepage") == []
