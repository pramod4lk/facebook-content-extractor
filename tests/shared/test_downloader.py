from pathlib import Path

import httpx
import pytest

from facebook_extractor.shared.downloader import (
    DownloadError,
    build_filename,
    download_media,
    sanitize_path_component,
)


def make_httpx_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_successful_image_download_writes_file(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Type": "image/jpeg"}, content=b"jpeg-bytes")

    path = download_media(
        make_httpx_client(handler),
        "https://scontent.example.com/1.jpg",
        tmp_path,
        media_id="123",
        media_kind="photo",
    )

    assert path == tmp_path / "123.jpg"
    assert path.read_bytes() == b"jpeg-bytes"
    assert not (tmp_path / ".123.part").exists()


def test_successful_video_download_writes_file(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Type": "video/mp4"}, content=b"mp4-bytes")

    path = download_media(
        make_httpx_client(handler),
        "https://scontent.example.com/9.mp4",
        tmp_path,
        media_id="9",
        media_kind="reel",
    )

    assert path == tmp_path / "9.mp4"
    assert path.read_bytes() == b"mp4-bytes"


def test_creates_destination_directory(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Type": "image/jpeg"}, content=b"x")

    destination = tmp_path / "Example Page" / "photos"

    path = download_media(
        make_httpx_client(handler), "https://x.example.com/1.jpg", destination,
        media_id="1", media_kind="photo",
    )

    assert path.parent == destination


def test_rejects_non_https_url(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x")

    with pytest.raises(DownloadError, match="non-HTTPS"):
        download_media(
            make_httpx_client(handler), "http://x.example.com/1.jpg", tmp_path,
            media_id="1", media_kind="photo",
        )


def test_permanent_http_failure_raises_and_leaves_no_partial_file(tmp_path: Path) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(404)

    with pytest.raises(DownloadError, match="HTTP 404"):
        download_media(
            make_httpx_client(handler), "https://x.example.com/1.jpg", tmp_path,
            media_id="1", media_kind="photo", sleep_fn=lambda _s: None,
        )

    assert len(calls) == 1
    assert list(tmp_path.iterdir()) == []


def test_retries_transient_http_failure_then_succeeds(tmp_path: Path) -> None:
    responses = iter([httpx.Response(503), httpx.Response(200, content=b"ok")])

    def handler(request: httpx.Request) -> httpx.Response:
        return next(responses)

    path = download_media(
        make_httpx_client(handler), "https://x.example.com/1.jpg", tmp_path,
        media_id="1", media_kind="photo", sleep_fn=lambda _s: None,
    )

    assert path.read_bytes() == b"ok"


def test_network_failure_raises_download_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(DownloadError, match="Network error"):
        download_media(
            make_httpx_client(handler), "https://x.example.com/1.jpg", tmp_path,
            media_id="1", media_kind="photo", sleep_fn=lambda _s: None,
        )

    assert list(tmp_path.iterdir()) == []


class TestBuildFilename:
    def test_prefers_content_type_over_url_extension(self) -> None:
        name = build_filename(
            "123", content_type="image/png", source_url="https://x.com/a.jpg", media_kind="photo"
        )
        assert name == "123.png"

    def test_falls_back_to_url_extension(self) -> None:
        name = build_filename(
            "123", content_type=None, source_url="https://x.com/a.mov", media_kind="reel"
        )
        assert name == "123.mov"

    def test_falls_back_to_media_kind_default(self) -> None:
        photo = build_filename("123", content_type=None, source_url=None, media_kind="photo")
        reel = build_filename("123", content_type=None, source_url=None, media_kind="reel")
        assert photo == "123.jpg"
        assert reel == "123.mp4"

    def test_ignores_unrecognized_content_type(self) -> None:
        name = build_filename(
            "123", content_type="application/octet-stream", source_url=None, media_kind="photo"
        )
        assert name == "123.jpg"


class TestSanitizePathComponent:
    def test_strips_path_traversal_and_separators(self) -> None:
        result = sanitize_path_component("../../etc/passwd", fallback="x")
        assert "/" not in result
        assert "\\" not in result
        assert result not in (".", "..", "")

    def test_replaces_invalid_filesystem_characters(self) -> None:
        result = sanitize_path_component('weird:"name"|<>?*', fallback="x")
        assert not any(char in result for char in '<>:"|?*')

    def test_falls_back_when_empty_after_sanitizing(self) -> None:
        assert sanitize_path_component("   ", fallback="fallback-name") == "fallback-name"
        assert sanitize_path_component(".", fallback="fallback-name") == "fallback-name"

    def test_caps_length(self) -> None:
        result = sanitize_path_component("a" * 500, fallback="x")
        assert len(result) <= 200
