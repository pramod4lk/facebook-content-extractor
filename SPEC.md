Facebook Page Photos & Reels Extractor
Specification Version: 2.0 (supersedes 1.x's Meta Graph API approach entirely)
Status: Implemented. Unofficial scraping tool — not affiliated with or endorsed by Meta.
Target Runtime: Python 3.12+
Application Type: Local CLI application
Primary Mechanism: unofficial HTML scraping of Facebook's public mobile site — NOT the
Meta Graph API. See §8 for why, and §19 for the risks this deliberately accepts.

## 1. Purpose

A local Python CLI that, given any public Facebook Page URL, downloads that Page's Photos
and Reels into an organized local directory — including Pages the user does not administer.

This is a deliberate pivot from v1.x, which used the official Meta Graph API. That approach
was correct and safe, but structurally could not deliver "any public Page": Photos required
a Page Access Token (only works for Pages you administer) or Meta's gated Pages Public
Content Access grant (business verification + app review), and Reels have no read endpoint
in the Graph API at all, for anyone, under any grant (confirmed against Meta's docs — see
git history for the v1.x findings). Achieving "any given public Page" requires giving up the
official API entirely. §19 documents exactly what that trade-off costs.

No web server. Primary command: `python -m facebook_extractor`.

## 2. Workflow

`.env` → Config Loader → Config Validation → URL Validation → Scan Photos listing ∥ Scan
Reels listing → per-item page fetch (resolve real media URL) → Duplicate Check → Downloader
→ Local Filesystem → Update Download Manifest → Extraction Summary

## 3. Configuration (`.env`)

```
FACEBOOK_PAGE_URL=https://www.facebook.com/examplepage   # required
OUTPUT_DIRECTORY=./downloads                                # optional, default shown
LOG_LEVEL=INFO                                              # optional, default shown
```

No credentials of any kind are collected, stored, or transmitted — there is nothing to
protect, because nothing is authenticated. This is a direct simplification over v1.x
(dropped `META_ACCESS_TOKEN`, `META_GRAPH_API_VERSION`).

- CFG-001: config MUST load from `.env` and be validated before any request is made.
- CFG-002: repo MUST include `.env.example` matching the keys above.
- CFG-003: `.gitignore` MUST exclude `.env`, `.env.*` (not `.env.example`), `downloads/`, `*.db`/`*.sqlite*`, `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.ruff_cache/`, `.venv/`/`venv/`.

## 4. Functional Requirements

- **FR-001 Load Configuration** — load `.env`; required: `FACEBOOK_PAGE_URL`; optional: `OUTPUT_DIRECTORY`, `LOG_LEVEL`. Validate before any request.
- **FR-002 Facebook Page URL** — accept `facebook.com/<page>` with/without `www.`/trailing slash, `m.facebook.com`, and `profile.php?id=`; normalize; ignore irrelevant query params; invalid URLs MUST produce a clear config error.
- **FR-003 Discover Photos** — crawl the Page's public photos listing (§8) and resolve each discovered item's direct image URL. No page-identity "resolution" step exists or is needed — the URL's slug/ID is used directly.
- **FR-004 Discover Reels** — crawl the Page's public videos listing (§8) and resolve each discovered item's direct video URL.
- **FR-005 Listing Pagination** — follow "more" pagination links in a listing page (§8) until none is found, a fetch fails, or `--limit` is reached (independently per media type, see CLI-004). A safety cap of 20 pages applies regardless (not a Facebook-documented limit — just a sane ceiling).
- **FR-006 Per-Item Resolution Is Best-Effort** — a single item whose media URL can't be resolved (markup mismatch, transient fetch failure) is skipped with a warning, not fatal to the whole run. A failure fetching the *first* listing page for a media type IS fatal for that type (reported as a limitation) but never aborts the other media type.
- **FR-007 Download Photos** → `<OUTPUT_DIRECTORY>/<page_slug>/photos/`
- **FR-008 Download Reels** → `<OUTPUT_DIRECTORY>/<page_slug>/reels/`
- **FR-009 Deterministic Filenames** — `<media_id>.<extension>`, where `media_id` is the `fbid` (Photos) or numeric path segment (Reels) extracted from the item's URL, falling back to a hash of the URL if none is found. Extension is derived in order: (1) response `Content-Type` header, (2) the source URL's own extension, (3) default `.jpg` (Photos) / `.mp4` (Reels).
- **FR-010 Safe Filenames** — sanitize all filenames/path segments; prevent path traversal, invalid filesystem characters, unexpected directory creation, excessively long names.
- **FR-011 Duplicate Detection** — primary key is the derived media ID, scoped per page slug + media type; already-downloaded media is SKIPPED by default.
- **FR-012 Force Download** — `--force` re-downloads existing media.
- **FR-013 Download Manifest** — SQLite manifest (single `.db` file) tracking `page_id` (the page slug), `media_type`, `media_id`, `source_url`, `local_filename`, `download_status` (`pending`/`downloaded`/`failed`/`skipped`), `downloaded_at`.
- **FR-014 Resumable Extraction** — a re-run skips previously-downloaded media and retries previously-failed media, unless `--force` is set.

## 5. CLI Requirements

| Flag | Behavior |
|---|---|
| `python -m facebook_extractor` (CLI-001) | Default: Photos + Reels; Page URL always from `.env` |
| `--photos` (CLI-002) | Photos only |
| `--reels` (CLI-003) | Reels only |
| `--limit N` (CLI-004) | Cap applies independently per media type |
| `--force` (CLI-005) | Re-download existing media |
| `--verbose` (CLI-006) | Debug-level logging |

## 6. CLI Output

Clear terminal output: Page slug, per-type scan/download progress, and a final summary
(found/downloaded/skipped/failed per media type, output path). The banner and any
limitation message MUST make clear this is not the official Meta API (see §19) — users
should not mistake results for an authoritative, complete listing.

## 7. Data Models

- **Photo**: `id`, `permalink`, `download_url` (optional — a discovered item with no resolvable URL is dropped, not modeled with a null field pretending richer metadata exists)
- **Reel**: same shape as Photo.

Deliberately smaller than a Graph-API-backed model would be (no caption, dimensions,
timestamps, duration) — scraping a listing/permalink page does not reliably expose these,
and modeling fields that are usually `None` in practice is worse than not having them.

## 8. Scraping Requirements (replaces "Meta Graph API Requirements")

This tool does not use the Meta Graph API. It fetches Facebook's own public pages with a
plain HTTP GET — no login, no cookies/session, no JavaScript execution, no CAPTCHA-solving,
no browser automation, no anti-bot evasion — and extracts data already embedded in those
pages for any unauthenticated visitor (the same data a browser or a link-preview crawler
would see).

- **SCRAPE-001** All such requests go through `shared/scraping.py` (`fetch_html`), which also detects and clearly fails on a login-wall response rather than trying to push through it.
- **SCRAPE-002** Listing pages are fetched from Facebook's lighter mobile interface (`m.facebook.com/<page_slug>/photos` and `/videos`) rather than the JS-heavy desktop site, since it's the closest thing to a scrapable server-rendered listing Facebook still serves.
- **SCRAPE-003** Item permalinks are found via regex over the listing HTML (`photos/scraper.py`, `reels/scraper.py`); each permalink is then fetched individually to extract its actual media URL (`og:image` for Photos; `playable_url`/`og:video` patterns for Reels).
- **SCRAPE-004** Pagination follows a "more" link found in the listing HTML (§4 FR-005); there is no documented cursor format to rely on, so this is inherently best-effort.
- **SCRAPE-005** No retry-with-backoff is applied to scraping requests specifically (contrast with the Downloader's retry in §11): a failed scrape is usually a broken assumption about page structure or a block, not a transient blip, and retrying blocked/detection-sensitive requests is itself a step toward the anti-bot-evasion this tool explicitly avoids.
- **SCRAPE-006** Every regex/pattern here is unversioned and will break silently whenever Facebook changes its markup — there is no upgrade path except updating the patterns after observing real breakage. Do not add complexity trying to make this "robust" against arbitrary future markup; keep patterns simple and let failures surface clearly (§19).

## 9. Architecture

**Vertical slice architecture**: code grouped by feature (photos, reels), not layer. Each
slice owns its `models.py` + `scraper.py` + tests. `shared/` holds only what's genuinely
identical across slices.

```
facebook-media-extractor/
├── src/facebook_extractor/
│   ├── __init__.py, __main__.py, cli.py, config.py
│   ├── shared/
│   │   ├── scraping.py      # fetch_html (login-wall detection) + generic pagination-follow loop
│   │   ├── url_parser.py    # Page URL validation/normalization
│   │   ├── downloader.py    # streaming download + filename sanitization/extension derivation
│   │   ├── retry.py         # exponential backoff (used by downloader.py only, see SCRAPE-005)
│   │   └── manifest.py      # SQLite download manifest
│   ├── photos/{models.py, scraper.py}
│   └── reels/{models.py, scraper.py}
├── tests/  (mirrors the above)
├── downloads/, .env.example, .gitignore, SPEC.md, README.md, pyproject.toml
```

No `page_resolution/` slice and no `shared/http_client.py` — there is no API to call and no
Page-identity resolution step; the URL's slug is used directly. `cli.py` orchestrates:
config → URL parsing → photos/reels scrapers → downloader → manifest → summary. Business
logic MUST NOT live in CLI argument handlers.

## 10. Security Requirements

Sanitize filenames; prevent path traversal; use HTTPS; never execute downloaded files;
apply sensible timeouts; don't trust external metadata blindly. No credentials exist to
leak (§3) — this removes an entire category of v1.x's security surface.

## 11. Downloader & Retry

Unchanged from v1.x: stream large files, HTTPS, 30s default timeout, auto-create
directories, safe atomic writes (temp file + rename), sequential (no concurrent
downloads), and a failure downloading one item MUST NOT abort the run. Retry transient
network failures / 5xx with exponential backoff (max 3 attempts, 1s/2s/4s, honoring
`Retry-After`) — this is about ordinary network flakiness fetching an already-resolved
media URL, distinct from SCRAPE-005's "don't retry a broken scrape" rule.

## 12. Error Handling & Logging

Handle gracefully: missing/invalid `.env`, invalid Page URL, a blocked/login-walled
listing or item fetch, network failures/timeouts, download failures, disk errors. Errors
must be actionable, e.g. "`FACEBOOK_PAGE_URL` is missing from `.env`." Exit code `0` on
full success; non-zero (e.g. `1`) on a config error or any failed/unavailable media type.

Logging: standard `logging`, default `LOG_LEVEL=INFO`, `--verbose` for debug detail. Log
startup, config validation, scan progress, pagination, download progress, duplicate
detection, retries, failures, completion summary.

## 13. Testing Requirements

`pytest`; no test makes a real request to facebook.com — all HTTP is mocked
(`httpx.MockTransport`). Cover: config (loading/missing/invalid); URL parser
(valid/invalid/trailing-slash/query-params/normalization); `shared/scraping`
(success/non-200/login-wall/pagination-follow/safety-cap); Photos & Reels scrapers
(discovery, per-item resolution, dedup, `--limit`, a single item's failure not being
fatal, the first listing page's failure being fatal for that type); Downloader
(image/video download, HTTP/network failure, filename generation, safe path handling);
Manifest (insert/lookup/update, duplicate detection, resume); CLI (default, `--photos`,
`--reels`, `--limit`, `--force`, `--verbose`).

## 14. Dependencies & Constraints

Prefer: Python 3.12+, `httpx`, `pydantic`, `pydantic-settings`, `python-dotenv`, `pytest`,
`ruff`. Unchanged from v1.x — the scraping approach needed no new dependency (`re`, `html`,
`urllib.parse` from the standard library). `pyproject.toml` with a standard build backend
(hatchling/setuptools); entry point `python -m facebook_extractor`.

MUST NOT use a web framework, Docker, or other infrastructure not already listed here
without asking first — this stays a simple local CLI. MUST NOT add a headless
browser/automation dependency (Playwright, Selenium, etc.) — that would cross from "read a
public page" into the browser-automation/anti-bot-evasion territory §19 explicitly rules
out; if the regex-based approach stops working, the fix is updating the regex, not adding
a browser.

## 15. Output Structure & Scope

```
downloads/<page_slug>/
├── .manifest.db
├── photos/<media_id>.jpg ...
└── reels/<media_id>.mp4 ...
```

**In scope**: `.env`-driven Page URL (any public Page), scraping-based Photos/Reels
discovery + pagination, downloading, duplicate detection, manifest, resume, CLI, logging,
error handling, tests, docs.
**Out of scope**: web UI, any web framework, cloud deployment/storage, distributed
processing, scheduled jobs, logging in or holding a session, bypassing a login wall or
CAPTCHA, browser automation, any other anti-bot/detection-evasion technique. Crossing any
of these requires the same explicit, informed sign-off documented in §19 — not an
assumption that "more scraping" is always fine because some scraping was already agreed to.

## 16. Definition of Done

`python -m facebook_extractor` loads/validates `.env`, discovers a given public Page's
Photos and Reels via scraping, handles pagination, detects duplicates, downloads into the
correct directories, maintains the manifest, resumes interrupted runs, reports failures
per item/media-type without aborting the whole job, prints a final summary that's honest
about not being the official API, passes tests and Ruff, and has complete setup/usage/risk
documentation.

## 17. Claude Code Instructions

Treat this SPEC.md as the source of truth. Prefer simple solutions; avoid unnecessary
abstractions. Never hard-code the Page URL. Never widen the scraping boundary in §19 (bulk
scope is already granted; login/session/CAPTCHA-bypass/browser-automation is not) without
the same explicit, informed sign-off from the project owner. When a scraping pattern breaks
against real Facebook markup, the fix is a narrowly-scoped regex/pattern update with a
test fixture capturing the new shape — not a rewrite toward heavier automation. Ask before
major architectural changes. If a requirement is ambiguous, surface the ambiguity before
making a major architectural decision.

## 18. Version History

- **v1.x** used the official Meta Graph API. Correct and safe, but could not deliver "any
  public Page": Photos needed a Page Access Token (Pages you administer) or Meta's gated
  Pages Public Content Access (business verification + app review); Reels had no read
  endpoint at all, for anyone. Superseded entirely by v2.0 at the project owner's explicit
  request, accepting the trade-offs in §19.
- **v2.0** (this version) drops the Graph API entirely in favor of unofficial scraping,
  achieving "any given public Page" for both Photos and Reels, in exchange for the risks
  in §19.

## 19. Risk Disclosure & Boundaries (read this before touching scraping code)

This is not a technicality — it's the central trade-off of this version of the project,
made explicitly and knowingly by the project owner after the Graph API path was shown to
structurally not support "any public Page."

**Accepted risks (not resolved by this spec — owned by the project owner):**
- **Violates Facebook's Terms of Service.** Automated data collection outside the official
  API is prohibited. Meta has pursued scraping operations before (cease-and-desist,
  account bans, litigation).
- **Fragile by construction.** Every pattern in `shared/scraping.py`, `photos/scraper.py`,
  and `reels/scraper.py` is unversioned. Facebook can and does change its markup without
  notice; this tool will break silently when that happens; there is no upgrade path except
  observing the breakage and updating the pattern.
- **No documented rate limit** applies (there's no API contract to read one from) — see
  SCRAPE-005 for why failures are treated as "pattern broke," not retried as transient.

**Hard boundaries that do NOT move without a fresh, explicit conversation with the project
owner** (bulk scraping itself was already explicitly approved; these are the next line):
- No login, no session, no cookies, no stored credentials of any kind.
- No CAPTCHA-solving.
- No browser automation (Playwright/Selenium/headless Chrome) or JS execution.
- No techniques whose purpose is evading detection/blocking (rotating user agents to look
  like different real users, proxy rotation to dodge IP blocks, mimicking real browser
  request timing, etc.). A plain, honestly-labeled `User-Agent` and a straightforward GET
  is the ceiling.
- No enumeration beyond what a page's own listing exposes (no guessing IDs, no hitting
  internal/undocumented GraphQL endpoints reverse-engineered from the app).

If achieving a future requirement would require crossing one of these, the correct action
is to stop and ask — the same way the Graph API's limitations were surfaced before this
pivot happened, not to silently escalate technique because a boundary was crossed once
before.
