import httpx
import pytest

from facebook_extractor.shared.scraping import ScrapeError, fetch_html, iter_listing_pages


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

    def test_login_wall_raises_scrape_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<title>Log into Facebook</title>")

        with pytest.raises(ScrapeError, match="login-required"):
            fetch_html(make_client(handler), "https://m.facebook.com/x")


class TestIterListingPages:
    def test_stops_when_no_next_link(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="page")

        pages = list(iter_listing_pages(make_client(handler), "https://x.com/1", lambda _h: None))

        assert pages == ["page"]

    def test_follows_next_link_until_exhausted(self) -> None:
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(200, text=f"page-{len(calls)}")

        def find_next(page_html: str) -> str | None:
            return "https://x.com/2" if page_html == "page-1" else None

        pages = list(iter_listing_pages(make_client(handler), "https://x.com/1", find_next))

        assert pages == ["page-1", "page-2"]
        assert len(calls) == 2

    def test_respects_max_pages_safety_cap(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="page")

        pages = list(
            iter_listing_pages(
                make_client(handler), "https://x.com/1", lambda _h: "https://x.com/1", max_pages=3
            )
        )

        assert len(pages) == 3

    def test_propagates_fetch_failures(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500)

        with pytest.raises(ScrapeError):
            list(iter_listing_pages(make_client(handler), "https://x.com/1", lambda _h: None))
