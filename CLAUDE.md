# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Facebook Content Extractor — a local CLI that downloads a public Facebook Page's Photos and
Reels, including Pages the user doesn't administer. Full behavioral spec: [SPEC.md](SPEC.md).
Setup/usage/risk disclosure: [README.md](README.md).

**This is an unofficial scraping tool, not a Meta Graph API integration** (v2.0 pivot — see
SPEC.md §18 Version History for why the Graph API approach was abandoned). Before touching
any scraping code, read SPEC.md §19 — it documents hard boundaries (no login/session/CAPTCHA
bypass/browser automation) that were deliberately NOT granted even though bulk scraping was.

`main.py`, `requirements.txt`, and `docker-compose.yml` at the repo root are leftover empty
placeholders from before SPEC.md was written — the real package lives at
`src/facebook_extractor/`, dependencies are declared in `pyproject.toml`, and Docker is
explicitly out of scope (SPEC.md §14). Don't add code to those root files.

## Environment

- Target Python 3.12+ (SPEC.md's floor; the committed `.venv` runs 3.14.4, which satisfies it).
- Activate the existing virtual environment before installing dependencies or running anything: `source .venv/bin/activate`

## Commands

- Install (editable, with dev deps): `pip install -e ".[dev]"`
- Lint: `ruff check .`
- Run tests: `pytest`
- Run a single test: `pytest tests/path/test_file.py::test_name`
- Run the app: `python -m facebook_extractor` (flags: `--photos`, `--reels`, `--limit N`, `--force`, `--verbose`)

## Architecture

**Vertical slice architecture** (SPEC.md §9): code is grouped by feature, not by technical
layer. Each slice owns its own `models.py` + `scraper.py` + tests.

- Slices: `photos/`, `reels/` — no `page_resolution/` slice exists; there's no API to
  resolve a Page identity against, so the URL's slug is used directly everywhere.
- `shared/`: `scraping.py` (`fetch_html` with login-wall detection + generic pagination-follow loop — used by both slices), `url_parser.py`, `downloader.py` (streaming download + filename sanitization/extension derivation), `manifest.py` (SQLite duplicate/resume tracking), `retry.py` (backoff, used by `downloader.py` only — see below).
- `cli.py` orchestrates: config → URL parsing → photos/reels scrapers → downloader → manifest → summary. Business logic MUST NOT live in CLI argument handlers — see `_scrape_and_process` in `cli.py` for where per-media-type logic belongs.
- Don't pre-extract something into `shared/` until at least two slices need the exact same code.

**Scraping failures are not retried** (SPEC.md SCRAPE-005), unlike downloader failures which
are. A broken scrape usually means Facebook's markup changed or the request got blocked —
retrying doesn't fix either, and retry-looping against a block is itself a step toward the
anti-bot-evasion this project explicitly avoids. Only `shared/downloader.py` uses
`shared/retry.py`'s backoff, for ordinary network flakiness fetching an already-resolved
media URL.

**When a scraping pattern breaks against real Facebook markup**: the fix is a narrowly
targeted regex/pattern update in `photos/scraper.py` or `reels/scraper.py`, plus a test
fixture capturing the new shape (SPEC.md §17). It is never a reason to reach for a headless
browser, a login flow, or anything else in SPEC.md §19's boundary list — those require a
fresh, explicit conversation with the project owner, the same way the original Graph API
limitations were surfaced rather than silently worked around.

## Coding Style

- Follow PEP 8.
- Use type hints on all function signatures.

## Do's

- Run `ruff check .` and `pytest` after writing new code, before considering it done.
- Create a new branch for each new development/feature rather than committing directly to `main`.
- Pin exact versions as needed in `pyproject.toml` for reproducible installs.
- Use `logging`, not `print`, for anything beyond user-facing CLI output.
- Mock all external HTTP in tests (`httpx.MockTransport`) — no test should make a real request to facebook.com (SPEC.md §13).

## Don'ts

- Don't commit `.env` files or extracted Facebook data/PII.
- Don't use bare `except:` — catch specific exceptions.
- Don't use mutable default arguments (`def f(x=[])`).
- Don't add retry/backoff around scraping requests (`shared/scraping.py`) — see SCRAPE-005 above; that's specific to `shared/downloader.py`.
- Don't introduce a web framework, Docker, headless browser/automation library, or other infrastructure not already in SPEC.md §14 without asking first.
- Don't add login, session/cookie handling, CAPTCHA-solving, or anti-bot evasion (user-agent/proxy rotation, request-timing mimicry) — SPEC.md §19's boundaries, not open for a unilateral judgment call.
