# facebook-content-extractor

A local Python CLI that extracts a Facebook Page's Photos (and, where Meta's API allows it,
Reels) via the official Meta Graph API and downloads them into an organized local folder.

Full behavioral spec: [SPEC.md](SPEC.md).

## Requirements

- Python 3.12+
- A **Page Access Token** for a Facebook Page you administer (Settings → moderator role),
  with the `pages_read_engagement` and `pages_show_list` permissions. A generic user token
  will not work for reading a Page's Photos.

> **Known limitation:** as of Meta Graph API v25.0, there is no endpoint to read/list a
> Page's *existing* Reels — `video_reels` is publish-only. The Reels extractor will always
> report this rather than silently returning nothing; see SPEC.md §7 (API-005) for details.
> Photos extraction works for Pages you administer today.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# then edit .env: FACEBOOK_PAGE_URL, META_ACCESS_TOKEN, META_GRAPH_API_VERSION
```

`.env` variables:

| Variable | Required | Default | Notes |
|---|---|---|---|
| `FACEBOOK_PAGE_URL` | yes | — | e.g. `https://www.facebook.com/examplepage` |
| `META_ACCESS_TOKEN` | yes | — | a Page Access Token, never committed or logged |
| `META_GRAPH_API_VERSION` | yes | — | e.g. `v25.0` |
| `OUTPUT_DIRECTORY` | no | `./downloads` | |
| `LOG_LEVEL` | no | `INFO` | |

## Usage

```bash
python -m facebook_extractor              # Photos + Reels
python -m facebook_extractor --photos     # Photos only
python -m facebook_extractor --reels      # Reels only
python -m facebook_extractor --limit 50   # cap per media type (50 photos AND 50 reels)
python -m facebook_extractor --force      # re-download media already in the manifest
python -m facebook_extractor --verbose    # debug-level logging
```

Output:

```
downloads/<page_name>/
├── .manifest.db      # SQLite download manifest (duplicate detection, resume)
├── photos/<media_id>.<ext>
└── reels/<media_id>.<ext>
```

Re-running the command resumes an interrupted extraction: already-downloaded media is
skipped, failed media is retried, unless `--force` is passed.

## Development

```bash
pytest          # run tests (all external HTTP is mocked; no real API calls)
ruff check .    # lint
```

Project layout follows vertical slice architecture — see [CLAUDE.md](CLAUDE.md) and
SPEC.md §8 for the full breakdown (`page_resolution/`, `photos/`, `reels/` slices, plus a
`shared/` package for the Graph API client, URL parser, downloader, and manifest).
