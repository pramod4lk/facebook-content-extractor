import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx

from facebook_extractor.config import ConfigurationError, Settings, load_settings
from facebook_extractor.photos.scraper import derive_media_id as derive_photo_id
from facebook_extractor.photos.scraper import fetch_photo_image_url
from facebook_extractor.reels.scraper import derive_media_id as derive_reel_id
from facebook_extractor.reels.scraper import fetch_reel_video_url
from facebook_extractor.shared.browser import BrowserResolutionError, LazyBrowser, resolve_media_url
from facebook_extractor.shared.downloader import DownloadError, download_media
from facebook_extractor.shared.logging_setup import configure_logging
from facebook_extractor.shared.manifest import DownloadStatus, Manifest, should_skip
from facebook_extractor.shared.scraping import ScrapeError

logger = logging.getLogger(__name__)

_REEL_HOSTS = ("fb.watch",)
_REEL_MARKERS = ("/reel/", "/reels/", "/videos/", "/watch", "video.php")
_PHOTO_MARKERS = ("/photo",)


@dataclass
class Summary:
    found: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0


def classify_url(url: str) -> Literal["photo", "reel"] | None:
    """Route a URL to its extractor by shape. Unrecognized URLs are reported and
    skipped, never guessed at."""
    lowered = url.lower()
    if urlparse(lowered).hostname in _REEL_HOSTS:
        return "reel"
    if any(marker in lowered for marker in _REEL_MARKERS):
        return "reel"
    if any(marker in lowered for marker in _PHOTO_MARKERS):
        return "photo"
    return None


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="facebook_extractor",
        description=(
            "Download specific public Facebook Photo/Reel URLs (unofficial — see SPEC.md §19)."
        ),
    )
    parser.add_argument("urls", nargs="*", help="One or more direct Photo/Reel URLs")
    parser.add_argument(
        "--urls-file",
        type=Path,
        default=None,
        metavar="PATH",
        help="Text file with one URL per line (for pasting a large batch); '#' lines ignored",
    )
    parser.add_argument("--force", action="store_true", help="Re-download existing media")
    parser.add_argument("--verbose", action="store_true", help="Increase log detail")
    parser.add_argument(
        "--headless",
        action="store_true",
        help=(
            "Run the browser fallback headless instead of visibly (SPEC.md §19: headful "
            "is the default — it looks more like a real user and lets you clear a "
            "checkpoint/CAPTCHA manually if one appears)"
        ),
    )
    return parser


def _collect_urls(args: argparse.Namespace) -> list[str]:
    urls = list(args.urls)
    if args.urls_file:
        for line in args.urls_file.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                urls.append(stripped)
    return urls


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        settings = load_settings()
    except ConfigurationError as exc:
        print(f"Configuration error:\n\n{exc}", file=sys.stderr)
        return 1

    configure_logging(settings.log_level, verbose=args.verbose)

    urls = _collect_urls(args)
    if not urls:
        print(
            "No URLs given. Pass one or more Photo/Reel URLs, or --urls-file PATH.",
            file=sys.stderr,
        )
        return 1

    return run_extraction(settings=settings, urls=urls, force=args.force, headless=args.headless)


def run_extraction(
    *, settings: Settings, urls: list[str], force: bool, headless: bool = False
) -> int:
    print("Facebook Media Extractor (unofficial — single-URL mode; see SPEC.md §19)")
    print("=========================================================================\n")

    client = httpx.Client()
    output_root = Path(settings.output_directory)
    manifest = Manifest(output_root / ".manifest.db")
    browser = LazyBrowser(headless=headless)
    summary = Summary()

    try:
        for url in urls:
            _process_one(
                url,
                output_root=output_root,
                manifest=manifest,
                force=force,
                client=client,
                browser=browser,
                summary=summary,
            )
    finally:
        manifest.close()
        client.close()
        browser.close()

    _print_summary(summary, output_root)
    return 1 if summary.failed > 0 else 0


def _process_one(
    url: str,
    *,
    output_root: Path,
    manifest: Manifest,
    force: bool,
    client: httpx.Client,
    browser: LazyBrowser,
    summary: Summary,
) -> None:
    media_kind = classify_url(url)
    if media_kind is None:
        print(f"Skipping (unrecognized URL type): {url}")
        summary.failed += 1
        return

    summary.found += 1

    if media_kind == "photo":
        media_id = derive_photo_id(url)
        fetch_media_url = fetch_photo_image_url
        subdir = "photos"
    else:
        media_id = derive_reel_id(url)
        fetch_media_url = fetch_reel_video_url
        subdir = "reels"

    existing_status = manifest.get_status(media_type=media_kind, media_id=media_id)
    if should_skip(existing_status, force=force):
        print(f"Skipping (already downloaded): {url}")
        summary.skipped += 1
        return

    try:
        download_url = fetch_media_url(client, url)
    except ScrapeError as plain_http_error:
        print(f"Plain HTTP extraction failed for {url} ({plain_http_error}); trying the browser...")
        try:
            download_url = resolve_media_url(browser.context(), url)
        except BrowserResolutionError as exc:
            print(f"Could not extract {url}:\n  {exc}")
            summary.failed += 1
            return

    try:
        final_path = download_media(
            client, download_url, output_root / subdir, media_id=media_id, media_kind=media_kind
        )
    except DownloadError as exc:
        logger.error("Failed to download %s (%s): %s", url, media_kind, exc)
        manifest.record(
            media_type=media_kind, media_id=media_id, source_url=download_url,
            status=DownloadStatus.FAILED,
        )
        print(f"Download failed for {url}:\n  {exc}")
        summary.failed += 1
        return

    manifest.record(
        media_type=media_kind,
        media_id=media_id,
        source_url=download_url,
        status=DownloadStatus.DOWNLOADED,
        local_filename=final_path.name,
    )
    print(f"Downloaded: {final_path}")
    summary.downloaded += 1


def _print_summary(summary: Summary, output_root: Path) -> None:
    print("\nExtraction complete.\n")
    print(f"Found:      {summary.found}")
    print(f"Downloaded: {summary.downloaded}")
    print(f"Skipped:    {summary.skipped}")
    print(f"Failed:     {summary.failed}\n")
    print(f"Output:\n{output_root}/")
