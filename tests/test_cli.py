import pytest

from facebook_extractor import cli
from facebook_extractor.shared.browser import BrowserResolutionError
from facebook_extractor.shared.scraping import ScrapeError


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OUTPUT_DIRECTORY", str(tmp_path / "downloads"))


@pytest.fixture(autouse=True)
def _fake_download(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_download_media(client, url, output_dir, *, media_id, media_kind):
        ext = "jpg" if media_kind == "photo" else "mp4"
        return output_dir / f"{media_id}.{ext}"

    monkeypatch.setattr(cli, "download_media", fake_download_media)


class _FakeBrowser:
    """Stands in for LazyBrowser in every test — never launches a real browser.
    context() just returns a sentinel; resolve_media_url decides success/failure."""

    def __init__(self, *, headless: bool = False) -> None:
        self.headless = headless

    def context(self) -> str:
        return "fake-context"

    def close(self) -> None:
        pass


def _browser_fallback_fails_by_default(context, url):
    raise BrowserResolutionError("browser fallback not mocked for this test")


@pytest.fixture(autouse=True)
def _fake_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "LazyBrowser", _FakeBrowser)
    monkeypatch.setattr(cli, "resolve_media_url", _browser_fallback_fails_by_default)


PHOTO_URL = "https://m.facebook.com/photo/?fbid=111"
REEL_URL = "https://m.facebook.com/reel/222/"


class TestClassifyUrl:
    @pytest.mark.parametrize(
        "url",
        ["https://m.facebook.com/reel/1/", "https://facebook.com/x/videos/1", "https://fb.watch/abc"],
    )
    def test_recognizes_reel_urls(self, url: str) -> None:
        assert cli.classify_url(url) == "reel"

    @pytest.mark.parametrize(
        "url", ["https://m.facebook.com/photo/?fbid=1", "https://facebook.com/photo.php?fbid=1"]
    )
    def test_recognizes_photo_urls(self, url: str) -> None:
        assert cli.classify_url(url) == "photo"

    def test_unrecognized_url_returns_none(self) -> None:
        assert cli.classify_url("https://facebook.com/somepage") is None


def test_downloads_a_mix_of_photo_and_reel_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "fetch_photo_image_url", lambda c, u: "https://x.com/111.jpg")
    monkeypatch.setattr(cli, "fetch_reel_video_url", lambda c, u: "https://x.com/222.mp4")

    exit_code = cli.main([PHOTO_URL, REEL_URL])

    assert exit_code == 0


def test_no_urls_returns_exit_code_1() -> None:
    assert cli.main([]) == 1


def test_urls_file_is_read_and_merged(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text(f"# a comment\n\n{PHOTO_URL}\n{REEL_URL}\n")

    seen: list = []
    monkeypatch.setattr(cli, "fetch_photo_image_url", lambda c, u: seen.append(u) or "https://x.com/1.jpg")
    monkeypatch.setattr(cli, "fetch_reel_video_url", lambda c, u: seen.append(u) or "https://x.com/2.mp4")

    exit_code = cli.main(["--urls-file", str(urls_file)])

    assert exit_code == 0
    assert seen == [PHOTO_URL, REEL_URL]


def test_unrecognized_url_is_skipped_and_counts_as_failed() -> None:
    exit_code = cli.main(["https://facebook.com/somepage"])

    assert exit_code == 1


def test_extraction_failure_for_one_url_does_not_abort_the_rest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_fetch(client, url):
        raise ScrapeError("Could not find a video URL in this page.")

    monkeypatch.setattr(cli, "fetch_reel_video_url", failing_fetch)
    monkeypatch.setattr(cli, "fetch_photo_image_url", lambda c, u: "https://x.com/111.jpg")

    exit_code = cli.main([REEL_URL, PHOTO_URL])

    assert exit_code == 1  # one failure means non-zero exit, but both URLs were attempted


def test_download_failure_counts_as_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    from facebook_extractor.shared.downloader import DownloadError

    monkeypatch.setattr(cli, "fetch_photo_image_url", lambda c, u: "https://x.com/111.jpg")

    def failing_download(client, url, output_dir, *, media_id, media_kind):
        raise DownloadError("HTTP 404")

    monkeypatch.setattr(cli, "download_media", failing_download)

    exit_code = cli.main([PHOTO_URL])

    assert exit_code == 1


def test_second_run_skips_already_downloaded_media(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []
    monkeypatch.setattr(
        cli, "fetch_photo_image_url", lambda c, u: calls.append(u) or "https://x.com/111.jpg"
    )

    cli.main([PHOTO_URL])
    cli.main([PHOTO_URL])

    assert calls == [PHOTO_URL]  # second run should skip before even fetching


def test_force_redownloads_existing_media(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []
    monkeypatch.setattr(
        cli, "fetch_photo_image_url", lambda c, u: calls.append(u) or "https://x.com/111.jpg"
    )

    cli.main([PHOTO_URL])
    cli.main(["--force", PHOTO_URL])

    assert calls == [PHOTO_URL, PHOTO_URL]


def test_verbose_enables_debug_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    levels: list = []
    monkeypatch.setattr(
        cli, "configure_logging", lambda level, *, verbose=False: levels.append((level, verbose))
    )

    cli.main(["--verbose"])

    assert levels == [("INFO", True)]


class TestBrowserFallback:
    def test_not_invoked_when_plain_http_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        browser_calls: list = []
        monkeypatch.setattr(cli, "fetch_photo_image_url", lambda c, u: "https://x.com/111.jpg")
        monkeypatch.setattr(
            cli, "resolve_media_url", lambda c, u: browser_calls.append(u) or "unused"
        )

        exit_code = cli.main([PHOTO_URL])

        assert exit_code == 0
        assert browser_calls == []

    def test_used_and_succeeds_when_plain_http_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def failing_fetch(client, url):
            raise ScrapeError("no video URL in this page")

        monkeypatch.setattr(cli, "fetch_reel_video_url", failing_fetch)
        monkeypatch.setattr(cli, "resolve_media_url", lambda c, u: "https://video.example.com/222.mp4")

        exit_code = cli.main([REEL_URL])

        assert exit_code == 0

    def test_failure_when_both_plain_http_and_browser_fail(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def failing_fetch(client, url):
            raise ScrapeError("no video URL in this page")

        monkeypatch.setattr(cli, "fetch_reel_video_url", failing_fetch)
        # _browser_fallback_fails_by_default (autouse) already makes resolve_media_url fail

        exit_code = cli.main([REEL_URL])

        assert exit_code == 1

    def test_headless_flag_is_passed_to_lazy_browser(self, monkeypatch: pytest.MonkeyPatch) -> None:
        instances: list = []
        real_init = _FakeBrowser.__init__

        def capturing_init(self, *, headless: bool = False) -> None:
            instances.append(headless)
            real_init(self, headless=headless)

        monkeypatch.setattr(_FakeBrowser, "__init__", capturing_init)

        def failing_fetch(client, url):
            raise ScrapeError("no video URL in this page")

        monkeypatch.setattr(cli, "fetch_reel_video_url", failing_fetch)
        monkeypatch.setattr(cli, "resolve_media_url", lambda c, u: "https://video.example.com/1.mp4")

        cli.main(["--headless", REEL_URL])

        assert instances == [True]
