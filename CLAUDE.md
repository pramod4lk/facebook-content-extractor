# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Facebook Content Extractor — a local CLI that extracts a Facebook Page's Photos (and Reels,
where Meta's API allows it) via the Meta Graph API. Full behavioral spec: [SPEC.md](SPEC.md).
Setup/usage: [README.md](README.md).

`main.py`, `requirements.txt`, and `docker-compose.yml` at the repo root are leftover empty
placeholders from before SPEC.md was written — the real package lives at
`src/facebook_extractor/`, dependencies are declared in `pyproject.toml`, and Docker is
explicitly out of scope for v1 (SPEC.md §14). Don't add code to those root files.

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

**Vertical slice architecture** (SPEC.md §8): code is grouped by feature, not by technical
layer. Each slice owns its own `service.py` + `models.py` + tests.

- Slices: `page_resolution/`, `photos/`, `reels/`.
- `shared/`: `http_client.py` (Graph API client — auth, pagination, retry/backoff, rate limits), `url_parser.py`, `downloader.py` (streaming download + filename sanitization), `manifest.py` (SQLite duplicate/resume tracking), `retry.py` (backoff shared by the client and downloader).
- `cli.py` orchestrates: config → URL parsing → page resolution → photos/reels services → downloader → manifest → summary. Business logic MUST NOT live in CLI argument handlers — see `_fetch_and_process` in `cli.py` for where per-media-type logic belongs.
- Don't pre-extract something into `shared/` until at least two slices need the exact same code.

**Confirmed API limitation** (SPEC.md §7 API-005, checked against current Meta docs): Graph
API v25.0 has no read/list endpoint for a Page's existing Reels — `video_reels` is
publish-only. `reels/service.py` still makes the real API call (so this self-heals if Meta
ever adds read support) but is expected to always raise `ReelExtractionError`; the CLI
reports this as a limitation for the Reels type and continues with Photos rather than
aborting the run.

## Coding Style

- Follow PEP 8.
- Use type hints on all function signatures.

## Do's

- Run `ruff check .` and `pytest` after writing new code, before considering it done.
- Create a new branch for each new development/feature rather than committing directly to `main`.
- Pin exact versions as needed in `pyproject.toml` for reproducible installs.
- Use `logging`, not `print`, for anything beyond user-facing CLI output.
- Store Facebook API tokens/credentials in environment variables or a `.env` file (already excluded via `.gitignore`) — never in source.
- Mock all external HTTP in tests (`httpx.MockTransport`) — no test should make a real Meta API request (SPEC.md §13).

## Don'ts

- Don't commit `.env` files, tokens, or extracted Facebook data/PII.
- Don't use bare `except:` — catch specific exceptions.
- Don't use mutable default arguments (`def f(x=[])`).
- Don't hammer Facebook's API/site without rate-limiting or backoff — aggressive requests risk throttling or bans.
- Don't introduce a web framework, Docker, or other infrastructure not already in SPEC.md §14 without asking first — v1 is explicitly scoped to a simple local CLI.
