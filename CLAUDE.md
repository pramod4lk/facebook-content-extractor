# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Facebook Content Extractor — extracts content from Facebook (see README.md). The repository is at an early scaffold stage: `main.py`, `requirements.txt`, and `docker-compose.yml` exist but are currently empty.

## Environment

- Target Python 3.14 (the committed `.venv` is built against 3.14.4) — use current-version syntax and stdlib features.
- Activate the existing virtual environment before installing dependencies or running anything: `source .venv/bin/activate`

## Commands

- Install dependencies: `pip install -r requirements.txt`
- Lint: `ruff check .`
- Run tests: `pytest`
- Run a single test: `pytest path/to/test_file.py::test_name`
- Run the app: `python main.py`
- Run via Docker Compose: `docker compose up --build`

`ruff` and `pytest` aren't declared in `requirements.txt` yet — add them (e.g. as dev dependencies) before these commands will work.

## Architecture

No code exists yet. See SPEC.md for the full spec; the project is organized using **vertical slice architecture**: group code by feature/capability, not by technical layer. Each slice owns everything it needs (API access, logic, models, tests) instead of being spread across shared `controllers/`, `services/`, `models/` folders.

- Slices (per SPEC.md §9): `page_resolution/`, `photos/`, `reels/` — each with its own `service.py`, `models.py`, and tests.
- `shared/` holds only what's genuinely identical across slices: the Meta Graph API HTTP client, URL parser, media downloader, and SQLite manifest. Don't pre-extract something into `shared/` until at least two slices need the exact same code.
- A slice should be understandable and modifiable on its own; avoid coupling one slice's internals to another's.
- `cli.py` orchestrates: config → URL parsing → page resolution → photos/reels services → downloader → manifest → summary. Business logic MUST NOT live in CLI argument handlers.

## Coding Style

- Follow PEP 8.
- Use type hints on all function signatures.

## Do's

- Run `ruff check .` after writing new code, before considering it done.
- Create a new branch for each new development/feature rather than committing directly to `main`.
- Pin exact versions in `requirements.txt` (`package==x.y.z`) for reproducible installs, since this also runs in Docker.
- Use `logging`, not `print`, for anything beyond a throwaway script.
- Store Facebook API tokens/credentials in environment variables or a `.env` file (already excluded via `.gitignore`) — never in source.
- Use a session with explicit timeouts and rate-limit/error handling for any calls to Facebook's API.

## Don'ts

- Don't commit `.env` files, tokens, or extracted Facebook data/PII.
- Don't use bare `except:` — catch specific exceptions.
- Don't use mutable default arguments (`def f(x=[])`).
- Don't hammer Facebook's API/site without rate-limiting or backoff — aggressive requests risk throttling or bans.
- Don't add a dependency to `requirements.txt` without pinning its version.
