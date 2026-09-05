from pathlib import Path

from facebook_extractor.shared.manifest import DownloadStatus, Manifest, should_skip


def make_manifest(tmp_path: Path) -> Manifest:
    return Manifest(tmp_path / "manifest.db")


def test_unknown_media_has_no_status(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)

    assert manifest.get_status(page_id="p1", media_type="photo", media_id="1") is None


def test_insert_and_lookup(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)

    manifest.record(
        page_id="p1",
        media_type="photo",
        media_id="1",
        source_url="https://x.com/1.jpg",
        status=DownloadStatus.DOWNLOADED,
        local_filename="1.jpg",
    )

    assert manifest.get_status(page_id="p1", media_type="photo", media_id="1") == (
        DownloadStatus.DOWNLOADED
    )


def test_update_overwrites_previous_status(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)

    manifest.record(
        page_id="p1", media_type="photo", media_id="1",
        source_url="https://x.com/1.jpg", status=DownloadStatus.FAILED,
    )
    manifest.record(
        page_id="p1", media_type="photo", media_id="1",
        source_url="https://x.com/1.jpg", status=DownloadStatus.DOWNLOADED,
        local_filename="1.jpg",
    )

    assert manifest.get_status(page_id="p1", media_type="photo", media_id="1") == (
        DownloadStatus.DOWNLOADED
    )


def test_records_are_scoped_per_page_and_media_type(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)

    manifest.record(
        page_id="p1", media_type="photo", media_id="1",
        source_url="https://x.com/1.jpg", status=DownloadStatus.DOWNLOADED,
    )

    assert manifest.get_status(page_id="p2", media_type="photo", media_id="1") is None
    assert manifest.get_status(page_id="p1", media_type="reel", media_id="1") is None


def test_persists_across_manifest_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "manifest.db"
    Manifest(db_path).record(
        page_id="p1", media_type="photo", media_id="1",
        source_url="https://x.com/1.jpg", status=DownloadStatus.DOWNLOADED,
    )

    reopened = Manifest(db_path)

    assert reopened.get_status(page_id="p1", media_type="photo", media_id="1") == (
        DownloadStatus.DOWNLOADED
    )


class TestShouldSkip:
    def test_skips_already_downloaded_by_default(self) -> None:
        assert should_skip(DownloadStatus.DOWNLOADED, force=False) is True

    def test_force_overrides_skip(self) -> None:
        assert should_skip(DownloadStatus.DOWNLOADED, force=True) is False

    def test_retries_failed_media_by_default(self) -> None:
        assert should_skip(DownloadStatus.FAILED, force=False) is False

    def test_downloads_unknown_media_by_default(self) -> None:
        assert should_skip(None, force=False) is False
