# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Facebook Content Extractor — a local CLI that downloads specific public Facebook Photos
and Reels given their direct URLs (not a Page URL — there's no bulk-discovery mode).
Full behavioral spec: [SPEC.md](SPEC.md). Setup/usage/risk disclosure: [README.md](README.md).

**This is an unofficial tool, not a Meta Graph API integration**, and it does not crawl a
Page's content automatically. **Read SPEC.md §19 in full before touching `shared/scraping.py`
or `shared/browser.py`** — it records three successive dead ends (Graph API → bulk listing
→ plain-HTTP permalinks) that each forced a real architecture change, and exactly what was
and wasn't approved when browser automation was finally added in v3.1. The boundaries that
survived that addition (no CAPTCHA-solving, no fingerprint/detection evasion, no bulk
discovery) are not loosened by the fact that login + browser automation were.

`main.py`, `requirements.txt`, and `docker-compose.yml` at the repo root are leftover empty
placeholders from before SPEC.md was written — the real package lives at
`src/facebook_extractor/`, dependencies are declared in `pyproject.toml`, and Docker is
explicitly out of scope (SPEC.md §14). Don't add code to those root files.

## Environment

- Target Python 3.12+ (SPEC.md's floor; the committed `.venv` runs 3.14.4, which satisfies it).
- Activate the existing virtual environment before installing dependencies or running anything: `source .venv/bin/activate`
- `playwright install chromium` is a one-time setup step beyond `pip install -e ".[dev]"` — the browser fallback needs an actual browser binary that pip doesn't fetch.

## Commands

- Install (editable, with dev deps): `pip install -e ".[dev]"` then `playwright install chromium`
- Lint: `ruff check .`
- Run tests: `pytest`
- Run a single test: `pytest tests/path/test_file.py::test_name`
- Run the app: `python -m facebook_extractor <url> [<url> ...]` or `--urls-file PATH` (flags: `--force`, `--verbose`, `--headless`)

## Architecture

**Vertical slice architecture** (SPEC.md §7): `photos/` and `reels/` each own one
`scraper.py` with three functions — `derive_media_id`, `extract_*_url`, `fetch_*_url`. No
`models.py` in either slice; a resolved item is just `(media_id, download_url)` passed
directly between functions.

- No `page_resolution/` slice, no `shared/http_client.py`, no `shared/url_parser.py` — there's no Page URL to resolve or validate. `cli.py::classify_url` does simple shape-based routing (path/host markers, including `fb.watch`) on whatever URL the user supplies.
- `shared/`: `scraping.py` (tier 1 — `fetch_html`, plain GET with login-wall detection via **both** the post-redirect URL and page text), `browser.py` (tier 2 — `LazyBrowser`/`resolve_media_url`, real Chromium under the user's own local login), `downloader.py`, `manifest.py` (no Page scoping — primary key is `(media_type, media_id)`), `retry.py` (used by `downloader.py` only).
- `cli.py::_process_one` tries tier 1 first; only on a `ScrapeError` does it call `browser.context()` (which lazily launches Chromium and prompts for login on first use) and try tier 2. If tier 1 keeps working, no browser is ever opened.

**Three real findings from live testing, not just theoretical risk** (SPEC.md §9):
1. Facebook's actual login-redirect response has no matching marker text in the body —
   text-only login-wall detection silently misreported "found nothing" instead of
   "blocked." Fixed by also checking whether the post-redirect URL lands on `/login`.
2. Bulk listing (`m.facebook.com/<page>/photos`, `/videos`) was tested against four real
   Pages of very different profiles — **all four hit the login wall, zero content
   served**. Don't rebuild bulk Page-level listing speculatively; it needs fresh evidence.
3. Individual permalinks (v3.0's fallback after finding #2) were *also* tested live — one
   real Reel URL, one real Photo URL, every URL shape (`www.`/`m.`/`mbasic.facebook.com`,
   `fb.watch`). Mobile paths hit the same login wall as #2. Desktop paths returned HTTP
   200 with **zero media data in the static HTML** — confirmed by grepping the raw
   response — because the actual media URL is fetched by the page's own JavaScript after
   load. This is why tier 2 (browser automation) exists; it isn't optional polish, tier 1
   alone resolved neither of the two real URLs tested.

**Scraping (tier 1) failures are not retried** (SPEC.md SCRAPE-004), unlike downloader
failures which are. Only `shared/downloader.py` uses `shared/retry.py`'s backoff, for
ordinary network flakiness fetching an already-resolved media URL.

**`shared/browser.py` is deliberately narrow** (SPEC.md SCRAPE-006/§19): it navigates to
one URL and observes the media network response the page itself requests
(`is_media_response` — content-type + CDN-hostname match), rather than reverse-engineering
Facebook's internal GraphQL contract. That predicate is the only part of this module
covered by automated tests — the actual Playwright orchestration (launching a browser,
navigating, intercepting) is never exercised by the test suite or by an agent, the same
policy as never making a real request to facebook.com extended to never launching a real
browser against it. It's validated by the project owner, on their own machine, under their
own login.

**When a scraping pattern breaks against real Facebook markup**: the fix is a narrowly
targeted regex/pattern update (tier 1) or an adjustment to `is_media_response`'s matching
(tier 2), plus a test fixture capturing the new shape (SPEC.md §14). It is never a reason
to add CAPTCHA-solving, fingerprint spoofing, proxy/UA rotation, or bulk enumeration —
those are still hard boundaries after v3.1, re-affirmed explicitly when browser automation
was added, not loosened by it (SPEC.md §19). If a future need seems to require crossing
one of them, that's a fresh, explicit conversation with the project owner — the same
pattern this project has followed at every previous dead end (Graph API limits → bulk
listing wall → plain-HTTP permalink wall → this).

## Coding Style

- Follow PEP 8.
- Use type hints on all function signatures.

## Do's

- Run `ruff check .` and `pytest` after writing new code, before considering it done.
- Create a new branch for each new development/feature rather than committing directly to `main`.
- Pin exact versions as needed in `pyproject.toml` for reproducible installs.
- Use `logging`, not `print`, for anything beyond user-facing CLI output.
- Mock all external HTTP in tests (`httpx.MockTransport`) — no test should make a real request to facebook.com, and none should launch a real browser (SPEC.md §14).
- Remove a module/class once nothing calls it (this codebase has done this repeatedly: `page_resolution/`, `shared/http_client.py`, `shared/url_parser.py`, both slices' `models.py`, and the entire listing/pagination layer were all deleted, not deprecated-in-place, once their callers were removed).

## Don'ts

- Don't commit `.env` files, extracted Facebook data/PII, or anything from `.browser_profile/` (the user's local login session).
- Don't use bare `except:` — catch specific exceptions.
- Don't use mutable default arguments (`def f(x=[])`).
- Don't add retry/backoff around tier-1 scraping requests (`shared/scraping.py`) — see SCRAPE-004; that's specific to `shared/downloader.py`.
- Don't rebuild bulk Page-level listing/discovery, in `shared/scraping.py` or via `shared/browser.py` — confirmed dead for tier 1, and explicitly still out of bounds for tier 2 (SPEC.md §19).
- Don't add CAPTCHA-solving, fingerprint spoofing, user-agent/proxy rotation, or any other detection-evasion technique beyond "a real browser, logged in as a real person" — re-affirmed as a hard boundary in the same conversation that approved browser automation, not loosened by it.
- Don't extend `shared/browser.py` toward general-purpose automation (auto-login flows, scripted interaction beyond navigate-and-observe, multi-session management) without the same explicit sign-off its initial addition required.
- Don't introduce a web framework, Docker, or other infrastructure not already in SPEC.md §14 without asking first.
