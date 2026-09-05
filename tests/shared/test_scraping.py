import httpx
import pytest

from facebook_extractor.shared.scraping import ScrapeError, fetch_html


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


class TestFetchHtml:
    def test_returns_body_on_success(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert "facebook-extractor" in request.headers["User-Agent"]
            return httpx.Response(200, text="<html>ok</html>")

        assert fetch_html(make_client(handler), "https://m.facebook.com/x") == "<html>ok</html>"

    def test_non_200_raises_scrape_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        with pytest.raises(ScrapeError, match="HTTP 404"):
            fetch_html(make_client(handler), "https://m.facebook.com/x")

    def test_redirect_to_login_raises_scrape_error(self) -> None:
        """Regression test: a real facebook.com /photos or /videos request that isn't
        publicly viewable 302s to /login/?next=... with a blank, marker-free body —
        this must be caught by inspecting the final URL, not by text-matching the page."""

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/x/photos":
                return httpx.Response(
                    302, headers={"Location": "https://m.facebook.com/login/?next=%2Fx%2Fphotos"}
                )
            return httpx.Response(200, text="")  # the real login page has no marker text

        with pytest.raises(ScrapeError, match="redirected .* to a login page"):
            fetch_html(make_client(handler), "https://m.facebook.com/x/photos")

    def test_login_wall_raises_scrape_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<title>Log into Facebook</title>")

        with pytest.raises(ScrapeError, match="login-required"):
            fetch_html(make_client(handler), "https://m.facebook.com/x")
