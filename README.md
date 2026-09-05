# facebook-content-extractor

A local Python CLI that downloads a public Facebook Page's Photos and Reels — including
Pages you don't administer.

Full behavioral spec: [SPEC.md](SPEC.md).

> **This is an unofficial scraping tool, not a Meta Graph API integration.** It works on
> any public Page precisely because it doesn't rely on API grants Meta would otherwise
> have to approve — but that means it violates Facebook's Terms of Service, and it's
> fragile: Facebook can change its page markup at any time with no notice, and this tool
> will break silently when that happens. See "Risks and boundaries" below before using it.

## Requirements

- Python 3.12+
- No Facebook account, token, or API credentials of any kind.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# then edit .env: set FACEBOOK_PAGE_URL to the public Page you want
```

`.env` variables:

| Variable | Required | Default | Notes |
|---|---|---|---|
| `FACEBOOK_PAGE_URL` | yes | — | e.g. `https://www.facebook.com/examplepage` |
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
downloads/<page_slug>/
├── .manifest.db      # SQLite download manifest (duplicate detection, resume)
├── photos/<media_id>.<ext>
└── reels/<media_id>.<ext>
```

Re-running the command resumes an interrupted extraction: already-downloaded media is
skipped, failed media is retried, unless `--force` is passed.

## How it works

There is no Facebook API call anywhere in this tool. It fetches the Page's public listing
pages on Facebook's lighter mobile site (`m.facebook.com/<page>/photos` and `/videos`)
with a plain HTTP GET — the same request an ordinary logged-out browser would make — and
extracts item links and media URLs from data already embedded in that HTML (`og:image`
for Photos, `og:video`/embedded player URLs for Reels). Pagination follows whatever "more"
link is present in the page; there's no documented cursor format, so this is inherently
best-effort.

## Risks and boundaries

**Accepted, not resolved by this tool:**
- **Violates Facebook's Terms of Service.** Automated data collection outside the
  official API is prohibited; Meta has pursued scraping operations before.
- **Will break without warning.** Every pattern this tool relies on is unversioned.
  Facebook changing its page markup is expected to eventually break extraction — that's
  not a bug in the traditional sense, it's the nature of scraping an unofficial interface.
- **No official rate limit** exists to respect, so failures are treated as "the page
  structure changed or we got blocked," not something to retry through.

**What this tool will never do, even to fix breakage** (see SPEC.md §19 for the full
reasoning): log in or hold a session, solve a CAPTCHA, run a headless browser or execute
JavaScript, rotate user agents/proxies to evade detection, or hit undocumented internal
endpoints beyond what a page's own public listing exposes. If a future need requires
crossing one of these, that's a conversation to have explicitly — not something to slide
into because scraping itself was already agreed to.

## Development

```bash
pytest          # run tests (all HTTP is mocked; no real requests to facebook.com)
ruff check .    # lint
```

Project layout follows vertical slice architecture — see [CLAUDE.md](CLAUDE.md) and
SPEC.md §9 (`photos/`, `reels/` slices, plus a `shared/` package for the HTML fetcher,
URL parser, downloader, retry helper, and manifest).
