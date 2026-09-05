import argparse
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx

from facebook_extractor.config import ConfigurationError, Settings, load_settings
from facebook_extractor.page_resolution.service import PageResolutionError, resolve_page
from facebook_extractor.photos.service import PhotoExtractionError, fetch_photos
from facebook_extractor.reels.service import ReelExtractionError, fetch_reels
from facebook_extractor.shared.downloader import (
    DownloadError,
    download_media,
    sanitize_path_component,
)
from facebook_extractor.shared.http_client import GraphAPIClient
from facebook_extractor.shared.logging_setup import configure_logging
from facebook_extractor.shared.manifest import DownloadStatus, Manifest, should_skip
from facebook_extractor.shared.url_parser import InvalidFacebookUrlError, parse_page_url

logger = logging.getLogger(__name__)


@dataclass
class MediaTypeSummary:
    found: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0
    limitation: str | None = None


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="facebook_extractor",
        description="Extract a Facebook Page's Photos and Reels via the Meta Graph API.",
    )
    media_group = parser.add_mutually_exclusive_group()
    media_group.add_argument("--photos", action="store_true", help="Extract Photos only")
    media_group.add_argument("--reels", action="store_true", help="Extract Reels only")
    parser.add_argument("--limit", type=int, default=None, help="Max items per media type")
    parser.add_argument("--force", action="store_true", help="Re-download existing media")
    parser.add_argument("--verbose", action="store_true", help="Increase log detail")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        settings = load_settings()
    except ConfigurationError as exc:
        print(f"Configuration error:\n\n{exc}", file=sys.stderr)
        return 1

    configure_logging(settings.log_level, verbose=args.verbose)

    try:
        parsed_url = parse_page_url(settings.facebook_page_url)
    except InvalidFacebookUrlError as exc:
        print(f"Configuration error:\n\n{exc}", file=sys.stderr)
        return 1

    return run_extraction(
        settings=settings,
        page_slug=parsed_url.page_slug,
        do_photos=args.photos or not args.reels,
        do_reels=args.reels or not args.photos,
        limit=args.limit,
        force=args.force,
    )


def run_extraction(
    *,
    settings: Settings,
    page_slug: str,
    do_photos: bool,
    do_reels: bool,
    limit: int | None,
    force: bool,
) -> int:
    print("Facebook Media Extractor")
    print("========================\n")

    graph_client = GraphAPIClient(
        access_token=settings.meta_access_token.get_secret_value(),
        api_version=settings.meta_graph_api_version,
    )
    download_client = httpx.Client()
    summaries: dict[str, MediaTypeSummary] = {}

    try:
        try:
            page = resolve_page(graph_client, page_slug)
        except PageResolutionError as exc:
            print(f"Page resolution failed:\n\n{exc}", file=sys.stderr)
            return 1

        print(f"Page: {page.name}")
        print(f"URL: {settings.facebook_page_url}\n")

        page_dir_name = sanitize_path_component(page.name, fallback=page.id)
        output_root = Path(settings.output_directory) / page_dir_name
        manifest = Manifest(output_root / ".manifest.db")

        try:
            if do_photos:
                summaries["Photos"] = _fetch_and_process(
                    label="Photos",
                    media_kind="photo",
                    fetch=lambda: fetch_photos(graph_client, page.id, limit=limit),
                    extraction_error=PhotoExtractionError,
                    page_id=page.id,
                    output_dir=output_root / "photos",
                    manifest=manifest,
                    force=force,
                    download_client=download_client,
                )
            if do_reels:
                summaries["Reels"] = _fetch_and_process(
                    label="Reels",
                    media_kind="reel",
                    fetch=lambda: fetch_reels(graph_client, page.id, limit=limit),
                    extraction_error=ReelExtractionError,
                    page_id=page.id,
                    output_dir=output_root / "reels",
                    manifest=manifest,
                    force=force,
                    download_client=download_client,
                )
        finally:
            manifest.close()
    finally:
        graph_client.close()
        download_client.close()

    _print_summary(summaries, output_root)

    has_problems = any(s.failed > 0 or s.limitation for s in summaries.values())
    return 1 if has_problems else 0


def _fetch_and_process(
    *,
    label: str,
    media_kind: Literal["photo", "reel"],
    fetch: Callable[[], list[Any]],
    extraction_error: type[Exception],
    page_id: str,
    output_dir: Path,
    manifest: Manifest,
    force: bool,
    download_client: httpx.Client,
) -> MediaTypeSummary:
    print(f"Fetching {label.lower()}...")
    try:
        items = fetch()
    except extraction_error as exc:
        print(f"Not available: {exc}\n")
        return MediaTypeSummary(limitation=str(exc))

    print(f"Found: {len(items)}\n")
    print(f"Downloading {label.lower()}...")
    summary = MediaTypeSummary(found=len(items))

    for item in items:
        if not item.download_url:
            logger.warning("%s %s has no download URL; skipping", media_kind, item.id)
            summary.failed += 1
            continue

        existing_status = manifest.get_status(
            page_id=page_id, media_type=media_kind, media_id=item.id
        )
        if should_skip(existing_status, force=force):
            summary.skipped += 1
            continue

        try:
            final_path = download_media(
                download_client,
                item.download_url,
                output_dir,
                media_id=item.id,
                media_kind=media_kind,
            )
        except DownloadError as exc:
            logger.error("Failed to download %s %s: %s", media_kind, item.id, exc)
            manifest.record(
                page_id=page_id,
                media_type=media_kind,
                media_id=item.id,
                source_url=item.download_url,
                status=DownloadStatus.FAILED,
            )
            summary.failed += 1
            continue

        manifest.record(
            page_id=page_id,
            media_type=media_kind,
            media_id=item.id,
            source_url=item.download_url,
            status=DownloadStatus.DOWNLOADED,
            local_filename=final_path.name,
        )
        summary.downloaded += 1

    return summary


def _print_summary(summaries: dict[str, MediaTypeSummary], output_root: Path) -> None:
    print("Extraction complete.\n")
    for label, summary in summaries.items():
        print(label)
        print("-" * len(label))
        if summary.limitation:
            print(f"Not available: {summary.limitation}\n")
            continue
        print(f"Found:      {summary.found}")
        print(f"Downloaded: {summary.downloaded}")
        print(f"Skipped:    {summary.skipped}")
        print(f"Failed:     {summary.failed}\n")
    print(f"Output:\n{output_root}/")
