Facebook Page Photos & Reels Extractor
Specification Version: 1.2 (condensed; same normative content as 1.1)
Status: Implemented (v1) — see README.md for setup. Reels extraction is a confirmed
Meta API limitation, not a bug (§7 API-005).
Target Runtime: Python 3.12+
Application Type: Local CLI application
Primary API: Meta Graph API

## 1. Purpose

A local Python CLI that reads a Facebook Page URL and Meta credentials from `.env`, retrieves the Page's available Photos and Reels via the Meta Graph API, and downloads them into an organized local directory. No web server, no Page URL as a CLI argument — everything sensitive comes from `.env`.

Primary command: `python -m facebook_extractor`

## 2. Workflow

`.env` → Config Loader → Config Validation → URL Validation → Resolve Page → Retrieve Media (Photos ∥ Reels) → Duplicate Check → Downloader → Local Filesystem → Update Manifest → Extraction Summary

## 3. Configuration (`.env`)

```
FACEBOOK_PAGE_URL=https://www.facebook.com/examplepage   # required
META_ACCESS_TOKEN=                                         # required
META_GRAPH_API_VERSION=vXX.X                                # required
OUTPUT_DIRECTORY=./downloads                                 # optional, default shown
LOG_LEVEL=INFO                                               # optional, default shown
```

- CFG-001: Config MUST load from `.env` and be validated before any API request.
- CFG-002: repo MUST include `.env.example` with the same keys and no real credentials.
- CFG-003: `.gitignore` MUST exclude `.env`, `.env.*` (but not `.env.example`), `downloads/`, `*.db`/`*.sqlite*`, `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.ruff_cache/`, `.venv/`/`venv/`.
- CFG-004: secrets MUST NOT be hard-coded, logged, printed, committed, included in exception messages, or exposed via object `repr`/`str`.

## 4. Functional Requirements

- **FR-001 Load Configuration** — load from `.env`; required: `FACEBOOK_PAGE_URL`, `META_ACCESS_TOKEN`, `META_GRAPH_API_VERSION`; optional: `OUTPUT_DIRECTORY`, `LOG_LEVEL`. Validate before any API call.
- **FR-002 Facebook Page URL** — accept `facebook.com/<page>` with/without `www.`/trailing slash; normalize it; ignore query params that don't affect identity; invalid URLs MUST produce a clear config error.
- **FR-003 Resolve Facebook Page** — resolve the URL to a Page identity via the API (never assume URL → Page ID). Must account for auth, permissions, API version, Page availability, and API limitations; if resolution isn't possible, report the limitation clearly.
- **FR-004 Extract Photos** — retrieve Photos with metadata where permitted (`id`, `page_id`, `caption`, `width`, `height`, `created_at`, `permalink`, media URL, download URL). Fields may be absent — handle gracefully.
- **FR-005 Extract Reels** — same as Photos, plus `duration`. If Meta doesn't expose downloadable Reel media for the configured credentials/API version, report that limitation clearly.
- **FR-006 API Pagination** — follow pagination until no more results or `--limit` is reached (limit applies independently per media type, see CLI-004). Never assume one request returns everything.
- **FR-007 Download Photos** → `<OUTPUT_DIRECTORY>/<page_name>/photos/<media_id>.<ext>`
- **FR-008 Download Reels** → `<OUTPUT_DIRECTORY>/<page_name>/reels/<media_id>.<ext>`
- **FR-009 Deterministic Filenames** — filename is `<facebook_media_id>.<extension>`; if a media ID can't be used, generate a deterministic safe fallback. Extension is derived in order: (1) response `Content-Type` header, (2) extension in the source/download URL, (3) default `.jpg` (Photos) / `.mp4` (Reels).
- **FR-010 Safe Filenames** — sanitize all filenames; prevent path/directory traversal, invalid filesystem characters, unexpected directory creation, and excessively long names. Captions MUST NOT be used as filenames unsanitized.
- **FR-011 Duplicate Detection** — primary key is the Facebook Media ID; already-downloaded media is SKIPPED by default.
- **FR-012 Force Download** — `--force` allows re-downloading existing media.
- **FR-013 Download Manifest** — MUST maintain a SQLite manifest (single local `.db` file) tracking at least `media_id`, `page_id`, `media_type`, `source_url`, `local_filename`, `download_status` (`pending`/`downloaded`/`failed`/`skipped`), `downloaded_at`. Used to determine whether media was already downloaded.
- **FR-014 Resumable Extraction** — an interrupted run, re-run, SHOULD skip previously downloaded media and retry previously failed media (unless configured otherwise).

## 5. CLI Requirements

| Flag | Behavior |
|---|---|
| `python -m facebook_extractor` (CLI-001) | Default: extract Photos + Reels; Page URL always from `.env`, never a CLI arg |
| `--photos` (CLI-002) | Extract Photos only |
| `--reels` (CLI-003) | Extract Reels only |
| `--limit N` (CLI-004) | Cap applies **independently per media type** (`--limit 50` = up to 50 Photos AND up to 50 Reels, or just the one type if `--photos`/`--reels` is set); must not reset per pagination page |
| `--force` (CLI-005) | Re-download existing media |
| `--verbose` (CLI-006) | Increase log detail |

## 6. CLI Output

Clear terminal output showing Page identity, per-type fetch/download progress, and a final summary (found/downloaded/skipped/failed per media type, output path). MUST NOT display access tokens or other secrets. See example in git history (v1.1) if a template is needed.

## 7. Meta Graph API Requirements

- **API-001** Use the official Graph API only — MUST NOT bypass auth, permissions, CAPTCHAs, rate limits, access controls, or other Meta restrictions.
- **API-002** Graph API version MUST be configurable via `META_GRAPH_API_VERSION`, never hard-coded.
- **API-003** Access token MUST come from `META_ACCESS_TOKEN`; never committed or logged.
- **API-004** All API communication goes through one dedicated client (no raw HTTP calls scattered through the app). It SHOULD support: GET + query params, auth, pagination, timeouts, error handling, retries, rate-limit handling, logging, and **sequential execution only** (no concurrent requests in this version).
- **API-005 API Feasibility** — before implementation, verify current Meta docs for: Page URL resolution, Photos/Reels retrieval, required permissions, token type, availability of download URLs, restrictions on public Pages, API version, recent deprecations. Do not guess API behavior.

  **Confirmed findings (checked against current Meta for Developers docs, current API version v25.0):**
  - `GET /{page-id}/photos` is supported and returns Photo nodes + pagination. It requires either (a) a Page Access Token for a Page the caller can `MODERATE`, plus `pages_read_engagement` + `pages_show_list`, or (b) the gated **Pages Public Content Access** feature (business verification + app review) with a System User token, for Pages the caller doesn't administer.
  - `POST /{page-id}/video_reels` exists **for publishing new Reels only** — the docs explicitly state read/update/delete are unsupported on this edge. `GET /{page-id}/videos` is likewise unsupported for reading. **There is no Graph API endpoint to list or retrieve a Page's existing Reels/videos as of v25.0.** This is a platform limitation, not a permissions gap — FR-005's "clearly report the limitation" behavior is the correct (and only possible) implementation; do not attempt to work around it (e.g. via scraping).
  - Default `META_GRAPH_API_VERSION` should be `v25.0` in `.env.example`, kept configurable per API-002.

## 8. Architecture

**Vertical slice architecture**: code is grouped by feature (page resolution, photos, reels), not by technical layer. Each slice owns its service logic, models, and tests. A small `shared/` package holds only what's genuinely identical across slices — nothing extracted speculatively.

```
facebook-media-extractor/
├── src/facebook_extractor/
│   ├── __init__.py, __main__.py, cli.py, config.py
│   ├── shared/
│   │   ├── http_client.py   # Graph API client: auth, pagination, timeouts, retries, rate limits
│   │   ├── url_parser.py    # Page URL validation/normalization
│   │   ├── downloader.py    # streaming download + filename sanitization
│   │   └── manifest.py      # SQLite download manifest
│   ├── page_resolution/{service.py, models.py}
│   ├── photos/{service.py, models.py}
│   └── reels/{service.py, models.py}
├── tests/  (mirrors the above: test_config.py, test_cli.py, shared/, page_resolution/, photos/, reels/)
├── downloads/, .env.example, .gitignore, SPEC.md, README.md, pyproject.toml
```

Structure MAY be adjusted for a clear reason, but MUST preserve vertical-slice grouping (feature-owned service+models; `shared/` only for genuinely cross-slice code). CLI orchestrates: config → URL parsing → page resolution → photos/reels services → downloader → manifest → summary. Business logic MUST NOT live in CLI argument handlers.

**Responsibilities** — Config: `.env`/env vars/validation/typed settings. HTTP Client: all Graph API I/O incl. auth/pagination/retry/rate-limit. URL Parser: validation/normalization/identifier extraction. Downloader: streaming, filename sanitization+extension, file writes, error handling. Manifest: SQLite tracking, duplicate detection, resume. Page/Photo/Reel slices: their own API calls + response normalization + models, via the shared HTTP client, with no cross-slice coupling.

## 9. Data Models

- **Page**: `id`, `name`, `username`, `url` (only fields the API actually returns)
- **Media (generic)**: `id`, `page_id`, `media_type`, `source_url`, `download_url`, `filename`, `mime_type`, `created_at`, `downloaded_at`
- **Photo** adds: `width`, `height`, `caption`, `permalink`
- **Reel** adds: `duration`, `width`, `height`, `caption`, `permalink`

All external API fields MUST be treated as optional.

## 10. Downloader & Retry

Downloader MUST: stream large files (never load full videos into memory), use HTTPS, apply a 30s default timeout, handle HTTP/network errors, auto-create directories, support duplicate detection, write files safely, report (not abort on) per-item failures, and run **sequentially** (no concurrent downloads in this version).

Retry transient failures (network errors, 5xx, temporary rate limits) with exponential backoff: max 3 attempts, 1s/2s/4s delay, honoring a `Retry-After` header when present. Do NOT retry permanent failures (invalid credentials, missing permissions, invalid Page/media IDs) unless the error indicates a transient condition.

## 11. Error Handling & Logging

Handle gracefully: missing/invalid `.env` or config, invalid Page URL, Page resolution failure, invalid/expired token, missing permissions, Meta API errors, rate limiting, pagination failures, network failures/timeouts, missing/invalid media URLs, unsupported media, download failures, disk errors. Errors must be actionable (e.g. "`FACEBOOK_PAGE_URL` is missing from `.env`. Please configure a Facebook Page URL before running the extractor.") and never reveal secret values.

Exit codes: `0` on full success; non-zero (e.g. `1`) on config error, Page-resolution failure, or any failed download.

Logging: standard `logging` module, default `LOG_LEVEL=INFO`, `--verbose` increases detail. Log startup, config validation, Page resolution, API ops/pagination, media discovery, download progress, duplicate detection, retries, failures, and the completion summary. NEVER log `META_ACCESS_TOKEN` or any other credential.

## 12. Security Requirements

Keep secrets in `.env` (gitignored); validate external URLs; sanitize filenames; prevent path traversal; use HTTPS; avoid secret leakage; never execute downloaded files; apply sensible timeouts; avoid uncontrolled downloads; don't trust external metadata blindly.

## 13. Testing Requirements

`pytest`; no test makes a real Meta API request — all external HTTP is mocked. Cover: config (loading, required/missing/invalid vars, secret protection); URL parser (valid/invalid URL, trailing slash, query params, normalization); HTTP client (success, API/auth errors, pagination, retries); page/photo/reel services (success, pagination, missing fields, empty response, not-found/API failure); downloader (image/video download, HTTP/network failure, duplicates, filename generation, safe path handling); manifest (insert/lookup/update, status, duplicate detection, resume); CLI (default run, `--photos`, `--reels`, `--limit`, `--force`, `--verbose`).

## 14. Dependencies & Constraints

Prefer: Python 3.12+, `httpx`, `pydantic`, `pydantic-settings`, `python-dotenv`, `pytest`, `ruff`. Additional deps only with clear benefit — avoid unnecessary ones. Use `pyproject.toml` with a standard build backend (hatchling or setuptools); entry point is `python -m facebook_extractor`, no console-script needed.

MUST NOT use a web framework (Flask/FastAPI/Django) — this is a local CLI, though internals should be separated enough that a future web API wouldn't require rewriting extraction logic (building that API is out of scope now). MUST NOT introduce Docker, Redis, Celery, RabbitMQ, Kubernetes, PostgreSQL, cloud storage, or message queues unless a real future requirement demands it — v1 stays a simple local app.

## 15. Output Structure & Scope

```
downloads/<page_name>/
├── photos/<media_id>.jpg ...
└── reels/<media_id>.mp4 ...
```
`<page_name>` MUST be sanitized before use as a directory name.

**In scope**: `.env`-driven Page URL, Meta API config, Page resolution, Photos/Reels retrieval + pagination + metadata, downloading, duplicate detection, manifest, resume, CLI, logging, error handling, tests, docs.
**Out of scope**: web UI, Flask/FastAPI/Django, auth UI, Meta OAuth web flow, cloud deployment/storage, distributed processing, scheduled jobs, automatic token renewal, scraping that bypasses Meta access controls.

**Important limitation**: the app MUST only download media legitimately exposed via the API to the authenticated app — a public Page's visibility does NOT guarantee its Photos/Reels are API-accessible. If Meta blocks access to a Page, media type, field, or download URL, report that limitation rather than circumventing it.

## 16. Development Process

1. **Repository Inspection** — inspect existing code/deps/tests/config; preserve useful existing work.
2. **API Feasibility** — verify current Meta docs for Page URL resolution, Photos/Reels APIs, downloadable media URLs, permissions, token requirements, pagination, API version, and current limitations. No assumptions.
3. **Architecture Proposal** — repository + API feasibility assessment, recommended architecture/directory structure/data models/endpoints/permissions/downloader+manifest design/testing strategy/risks/implementation plan.
4. **Approval** — STOP after 1–3 and wait for explicit user approval before implementing substantial code. Do not silently proceed.

**Milestones** (after approval, adjustable if technically necessary): 1) project setup + config, 2) URL parser, 3) Meta API client, 4) Page resolution, 5) Photo extraction, 6) Reel extraction, 7) media downloader, 8) manifest + duplicate handling, 9) CLI + progress reporting, 10) testing + docs + cleanup.

**Quality gate** after every milestone: run tests, run Ruff, verify imports, check error handling/secret handling/filesystem safety, fix issues found, summarize changes, name the next milestone. Don't proceed with known failing tests unless the failure is explicitly explained.

## 17. Definition of Done

`python -m facebook_extractor` loads and validates `.env`, authenticates, resolves the Page, retrieves Photos and Reels with pagination, normalizes metadata, detects duplicates, downloads into the correct directories, maintains the manifest, resumes interrupted runs, reports failures without aborting the whole job, prints a final summary, never leaks credentials, passes tests and Ruff, and has complete setup/usage docs.

## 18. Claude Code Instructions

Treat this SPEC.md as the source of truth. Prefer simple solutions; avoid unnecessary abstractions or frameworks. Never hard-code secrets, the Page URL, or the API version. Never bypass Meta restrictions or silently change requirements. Ask before major architectural changes. If a requirement conflicts with actual Meta API behavior, prioritize the real API behavior and explain the limitation. If a requirement is ambiguous, surface the ambiguity before making a major architectural decision.

**First action in this repo**: do NOT implement immediately. Inspect the repo → read this spec → check Meta API feasibility → identify exact endpoints/permissions needed → produce an architecture proposal + implementation plan + risks → STOP and wait for approval.
