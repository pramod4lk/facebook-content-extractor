import pytest

from facebook_extractor import cli
from facebook_extractor.photos.models import Photo
from facebook_extractor.reels.models import Reel
from facebook_extractor.shared.scraping import ScrapeError

REQUIRED_ENV = {
    "FACEBOOK_PAGE_URL": "https://www.facebook.com/examplepage",
}


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("OUTPUT_DIRECTORY", str(tmp_path / "downloads"))


@pytest.fixture(autouse=True)
def _fake_download(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_download_media(client, url, output_dir, *, media_id, media_kind):
        return output_dir / f"{media_id}.jpg"

    monkeypatch.setattr(cli, "download_media", fake_download_media)


def _record_calls(calls: list, items: list):
    def list_fn(client, page_slug, *, limit=None):
        calls.append(limit)
        return items

    return list_fn


def test_default_execution_fetches_both_media_types(monkeypatch: pytest.MonkeyPatch) -> None:
    photo_calls: list = []
    reel_calls: list = []
    photo = Photo(id="1", permalink="https://m.facebook.com/photo/?fbid=1", download_url="https://x.com/1.jpg")
    monkeypatch.setattr(cli, "list_photos", _record_calls(photo_calls, [photo]))
    monkeypatch.setattr(cli, "list_reels", _record_calls(reel_calls, []))

    exit_code = cli.main([])

    assert exit_code == 0
    assert photo_calls == [None]
    assert reel_calls == [None]


def test_photos_flag_skips_reels(monkeypatch: pytest.MonkeyPatch) -> None:
    reel_calls: list = []
    monkeypatch.setattr(cli, "list_photos", _record_calls([], []))
    monkeypatch.setattr(cli, "list_reels", _record_calls(reel_calls, []))

    exit_code = cli.main(["--photos"])

    assert exit_code == 0
    assert reel_calls == []


def test_reels_flag_skips_photos(monkeypatch: pytest.MonkeyPatch) -> None:
    photo_calls: list = []
    monkeypatch.setattr(cli, "list_photos", _record_calls(photo_calls, []))
    monkeypatch.setattr(cli, "list_reels", _record_calls([], []))

    exit_code = cli.main(["--reels"])

    assert exit_code == 0
    assert photo_calls == []


def test_photos_and_reels_together_is_rejected() -> None:
    with pytest.raises(SystemExit):
        cli.main(["--photos", "--reels"])


def test_limit_is_passed_through_per_media_type(monkeypatch: pytest.MonkeyPatch) -> None:
    photo_calls: list = []
    reel_calls: list = []
    monkeypatch.setattr(cli, "list_photos", _record_calls(photo_calls, []))
    monkeypatch.setattr(cli, "list_reels", _record_calls(reel_calls, []))

    cli.main(["--limit", "50"])

    assert photo_calls == [50]
    assert reel_calls == [50]


def test_force_allows_redownload_of_completed_media(monkeypatch: pytest.MonkeyPatch) -> None:
    photo = Photo(id="1", permalink="https://m.facebook.com/photo/?fbid=1", download_url="https://x.com/1.jpg")
    monkeypatch.setattr(cli, "list_photos", _record_calls([], [photo]))
    monkeypatch.setattr(cli, "list_reels", _record_calls([], []))

    downloaded_calls: list = []

    def fake_download_media(client, url, output_dir, *, media_id, media_kind):
        downloaded_calls.append(media_id)
        return output_dir / f"{media_id}.jpg"

    monkeypatch.setattr(cli, "download_media", fake_download_media)

    cli.main(["--photos"])
    cli.main(["--photos"])  # second run: already downloaded, should be skipped
    assert downloaded_calls == ["1"]

    cli.main(["--photos", "--force"])
    assert downloaded_calls == ["1", "1"]


def test_verbose_enables_debug_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "list_photos", _record_calls([], []))
    monkeypatch.setattr(cli, "list_reels", _record_calls([], []))
    levels: list = []
    monkeypatch.setattr(
        cli,
        "configure_logging",
        lambda level, *, verbose=False: levels.append((level, verbose)),
    )

    cli.main(["--verbose"])

    assert levels == [("INFO", True)]


def test_missing_configuration_returns_exit_code_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FACEBOOK_PAGE_URL", raising=False)

    assert cli.main([]) == 1


def test_invalid_page_url_returns_exit_code_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FACEBOOK_PAGE_URL", "https://www.instagram.com/examplepage")

    assert cli.main([]) == 1


def test_reel_limitation_is_reported_but_does_not_fail_photos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    photo = Photo(id="1", permalink="https://m.facebook.com/photo/?fbid=1", download_url="https://x.com/1.jpg")
    monkeypatch.setattr(cli, "list_photos", _record_calls([], [photo]))

    def failing_list_reels(client, page_slug, *, limit=None):
        raise ScrapeError("Facebook returned a login-required page")

    monkeypatch.setattr(cli, "list_reels", failing_list_reels)

    exit_code = cli.main([])

    assert exit_code == 1  # a limitation still counts as "had problems" for exit code purposes


def test_item_without_download_url_counts_as_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    reel = Reel(id="1", permalink="https://m.facebook.com/reel/1/", download_url=None)
    monkeypatch.setattr(cli, "list_photos", _record_calls([], []))
    monkeypatch.setattr(cli, "list_reels", _record_calls([], [reel]))

    exit_code = cli.main(["--reels"])

    assert exit_code == 1
