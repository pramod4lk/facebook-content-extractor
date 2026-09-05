Facebook Page Photos & Reels Extractor
Specification Version: 3.1 (adds a browser-automation fallback under the user's own login)
Status: Implemented. Unofficial scraping tool — not affiliated with or endorsed by Meta.
Target Runtime: Python 3.12+
Application Type: Local CLI application
Primary Mechanism: unofficial per-item extraction of specific Facebook Photo/Reel URLs —
NOT the Meta Graph API, and NOT bulk Page-listing crawling. Two-tier resolution: a plain
HTTP fetch first, falling back to a real, locally-logged-in browser when that's not
enough. See §1, §9, and §19 for why, and for the exact boundary this still holds at.

## 1. Purpose

A local Python CLI that downloads specific public Facebook Photos and Reels, given their
direct URLs, into an organized local directory.

This is the third pivot for this project, each forced by hitting a real wall rather than
a hypothetical one:

- **v1.x** used the official Meta Graph API — couldn't reach Pages the user doesn't
  administer.
- **v2.0** dropped the Graph API for bulk scraping of a Page's `/photos`/`/videos`
  listing tabs — live testing found those universally redirect to a login page, for
  every Page tested regardless of size.
- **v3.0** shrank to specific item permalinks the user supplies (found by their own
  browsing) — but live testing of *those* found a second wall: desktop permalink pages
  return 200 with no media data at all (the video/image URL is fetched by JavaScript
  after page load, which a plain HTTP client never runs), while every mobile permalink
  path redirects to the same login wall as the listing tabs.
- **v3.1** (this version) adds a second resolution tier: when the plain HTTP fetch comes
  back empty, fall back to a real browser, logged in as the user, that actually runs the
  page's JavaScript and observes the media response it naturally requests. This is a
  deliberate, informed reversal of a boundary earlier versions of this spec called
  non-negotiable — see §19 for exactly what was reconsidered, what wasn't, and why.

No web server, no bulk enumeration, no Page-level concept at all. Primary command:

```
python -m facebook_extractor <url> [<url> ...]
python -m facebook_extractor --urls-file urls.txt
```

## 2. Workflow

URLs (positional args and/or `--urls-file`) → classify each by shape (Photo vs Reel) →
per-item page fetch (resolve the real media URL) → Duplicate Check → Downloader → Local
Filesystem → Update Download Manifest → Extraction Summary.

There is no "discover a Page's media" step (v2.0 had one; it's gone) and no Page-identity
concept (v1.x had one; also gone).

## 3. Configuration (`.env`)

```
OUTPUT_DIRECTORY=./downloads   # optional, default shown
LOG_LEVEL=INFO                 # optional, default shown
```

No credentials, tokens, or Page URL are configured — both remaining keys are optional. A
`.env` file isn't even required for the tool to run.

- CFG-001: `.gitignore` MUST exclude `.env`, `.env.*` (not `.env.example`), `downloads/`, `*.db`/`*.sqlite*`, `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.ruff_cache/`, `.venv/`/`venv/`.

## 4. Functional Requirements

- **FR-001 Load Configuration** — load `.env` if present; both `OUTPUT_DIRECTORY` and `LOG_LEVEL` are optional with defaults.
- **FR-002 Accept URLs** — via positional CLI arguments and/or `--urls-file PATH` (one URL per line; blank lines and `#`-prefixed lines ignored). At least one URL MUST be present or the run fails with a clear message (CLI-level, not a crash).
- **FR-003 Classify Each URL** — a URL is routed to the Photo or Reel extractor by shape (path/host markers — `cli.classify_url`). A URL matching neither is reported and skipped; it is never guessed at or forced through one extractor.
- **FR-004 Resolve Media URL (two-tier)** — first, a plain HTTP fetch of the permalink page (`og:image` for Photos; `playable_url`/`og:video` for Reels). If that finds nothing, fall back to rendering the page in a real, locally-logged-in browser and observing the media response it naturally requests (§19). A failure at both tiers for one URL is reported and counted as failed — it MUST NOT abort processing of the remaining URLs. The browser is launched lazily — only on the first plain-HTTP failure in a run — so a run where the plain fetch keeps working never opens one.
- **FR-005 Deterministic Filenames** — `<media_id>.<extension>`. `media_id` is the `fbid` query param (Photos) or a numeric path/query segment (Reels), falling back to a hash of the URL if none is found. Extension is derived in order: (1) response `Content-Type` header, (2) the resolved media URL's own extension, (3) default `.jpg` (Photos) / `.mp4` (Reels).
- **FR-006 Safe Filenames** — sanitize all filenames/path segments; prevent path traversal, invalid filesystem characters, excessively long names.
- **FR-007 Duplicate Detection** — primary key is `(media_type, media_id)`; already-downloaded media is SKIPPED by default, without even attempting to re-resolve its URL.
- **FR-008 Force Download** — `--force` re-downloads and re-resolves existing media.
- **FR-009 Download Manifest** — SQLite manifest (single `.db` file at `<OUTPUT_DIRECTORY>/.manifest.db`) tracking `media_type`, `media_id`, `source_url`, `local_filename`, `download_status` (`pending`/`downloaded`/`failed`/`skipped`), `downloaded_at`. No Page scoping (§9) — a run processes an arbitrary batch of URLs, possibly from different Pages.
- **FR-010 Resumable** — re-running with overlapping URLs skips previously-downloaded media and retries previously-failed media, unless `--force` is set.

## 5. CLI Requirements

| Flag | Behavior |
|---|---|
| `python -m facebook_extractor <url> [<url> ...]` (CLI-001) | Download the given URLs |
| `--urls-file PATH` (CLI-002) | Read additional URLs from a file, one per line |
| `--force` (CLI-003) | Re-download/re-resolve existing media |
| `--verbose` (CLI-004) | Debug-level logging |
| `--headless` (CLI-005) | Run the browser fallback headless instead of visibly. Default is visible (§19: looks more like a real user, and lets the user clear a checkpoint/CAPTCHA manually). |

No `--photos`/`--reels`/`--limit` — those were bulk-listing controls (v2.0) that no longer
apply; each URL already says what it is, and "how many" is just how many URLs you pass.

## 6. CLI Output

Per-URL progress line (skipped/downloaded/failed, with the reason for anything other than
a clean download) followed by a final summary (found/downloaded/skipped/failed, output
path). Output MUST make clear this is not the official Meta API (§19).

## 7. Architecture

**Vertical slice architecture**: `photos/` and `reels/` each own a `scraper.py` with three
functions: `derive_media_id(url)`, `extract_*_url(html) -> str`, `fetch_*_url(client, url) -> str`.
No `models.py` in either slice — a resolved item is just `(media_id, download_url)`, passed
directly between functions; a dataclass wrapping two fields added nothing.

```
facebook-media-extractor/
├── src/facebook_extractor/
│   ├── __init__.py, __main__.py, cli.py, config.py
│   ├── shared/
│   │   ├── scraping.py      # fetch_html: plain GET + login-wall detection (via response.url AND page text)
│   │   ├── browser.py       # LazyBrowser + resolve_media_url: the JS-rendering fallback (§19)
│   │   ├── downloader.py    # streaming download + filename sanitization/extension derivation
│   │   ├── retry.py         # exponential backoff (used by downloader.py only, see SCRAPE-004)
│   │   └── manifest.py      # SQLite download manifest, no Page scoping
│   ├── photos/scraper.py
│   └── reels/scraper.py
├── tests/  (mirrors the above)
├── downloads/, .browser_profile/ (gitignored — local login session), .env.example, .gitignore, SPEC.md, README.md, pyproject.toml
```

No `page_resolution/` slice, no `shared/http_client.py`, no `shared/url_parser.py` — there
is no Page URL to validate/normalize anymore; `classify_url` in `cli.py` does simple
shape-based routing on whatever URL was given, and that's the full extent of URL handling
needed. `cli.py` orchestrates: config → collect URLs → per-URL (classify → resolve →
duplicate check → download → manifest) → summary. Business logic MUST NOT live in CLI
argument handlers — see `_process_one` for where it belongs.

## 8. Data Model

A resolved item is `(media_id: str, download_url: str)` — nothing richer is reliably
extractable from a permalink page via simple pattern matching, and previous versions'
model classes carrying always-`None` fields (caption, dimensions, timestamps) were removed
rather than kept for a future that may not come.

## 9. Scraping Requirements

This tool does not use the Meta Graph API. Resolving a URL's real media URL is two-tier:
first a plain HTTP GET (no login, no cookies/session, no JavaScript, no CAPTCHA-solving);
if that finds nothing, a fallback to a real browser under the user's own local Facebook
login (§19) — still no CAPTCHA-solving, no fingerprint spoofing, no detection evasion
beyond "a real browser, logged in as a real person, looking at one page at a time."

- **SCRAPE-001** All tier-1 requests go through `shared/scraping.py::fetch_html`, which detects a login wall two ways: the final URL (after following redirects) landing on a `/login` path, and specific marker text in the page body. **The URL-based check is load-bearing**: real-world testing found Facebook's actual login-redirect response has no matching body text, so text-matching alone silently misreported "found nothing" instead of "blocked" (fixed during development).
- **SCRAPE-002 — Confirmed dead end, do not resurrect without new evidence.** Bulk listing (`m.facebook.com/<page>/photos` and `/videos`, v2.0's approach) was tested live against one small local-business Page and three large global brand Pages (six requests total) — **all six redirected straight to a login wall**, zero content served. Don't rebuild bulk Page-level listing speculatively; it needs fresh evidence, not an assumption that a better regex would fix it.
- **SCRAPE-003 — Also confirmed, tier-1 only reaches some content.** Live-tested against one real Reel URL and one real Photo URL, across every URL shape tried:
  - `m.facebook.com`, `mbasic.facebook.com` individual permalinks (both media types) → login wall, same as SCRAPE-002.
  - `www.facebook.com` individual permalinks (both media types) → HTTP 200, but the response is a client-rendered shell with **no media data in the HTML at all** (confirmed by direct inspection — a `video_id`/`fbid` was present in an internal JSON blob, but no `playable_url`, `og:video`, `og:image`, or `.mp4`/CDN reference anywhere in ~450KB of markup). The real media URL is fetched by a follow-up API call triggered by the page's own JavaScript after load — tier-1 never runs that JavaScript, so it never sees that call.
  - This is why tier-2 (§SCRAPE-006) exists: it isn't optional polish, tier-1 alone was found to resolve **zero** of the two real URLs tested.
- **SCRAPE-004** No retry-with-backoff on tier-1 scraping requests: a failed fetch is a broken assumption or a block, not a transient blip, and retrying a block is itself a step toward the anti-bot-evasion this tool avoids elsewhere. (Contrast `shared/downloader.py`, which does retry — ordinary network flakiness fetching an already-resolved media URL, a different failure class.)
- **SCRAPE-005** Every tier-1 regex/pattern is unversioned and will break silently whenever Facebook changes its markup. Keep patterns simple; let failures surface clearly rather than adding defensive complexity trying to anticipate arbitrary future markup.
- **SCRAPE-006 — Tier 2: browser fallback.** `shared/browser.py` launches a real Chromium browser (via Playwright) using a persistent local profile (`.browser_profile/`, gitignored) that holds the user's own Facebook login session — established once, manually, by the user, in a visible browser window (`ensure_logged_in`); this tool never sees or stores a password. `resolve_media_url` navigates to the URL and listens for the actual video/image network response the page requests while rendering (matched by content-type and CDN hostname — `shared/browser.py::is_media_response`) — this observes what Facebook's own JavaScript resolves, rather than reverse-engineering its internal GraphQL contract. Runs headful by default (§19); `--headless` opts into headless. Lazily initialized — only launched on the first tier-1 failure in a run.
- **SCRAPE-007** If the browser fallback hits a CAPTCHA or identity checkpoint, the tool MUST NOT attempt to solve or bypass it. It surfaces in the visible browser window for the user to resolve manually; the run should be repeated afterward. This applies even when running headless is otherwise the user's preference — a checkpoint is exactly the case headful mode exists for.

## 10. Downloader & Retry

Unchanged from earlier versions: stream large files, HTTPS, 30s default timeout,
auto-create directories, safe atomic writes (temp file + rename), sequential, a failure
on one item MUST NOT abort the run. Retry transient network failures/5xx with exponential
backoff (max 3 attempts, 1s/2s/4s, honoring `Retry-After`).

## 11. Error Handling & Logging

Handle gracefully: no URLs given, an unrecognized URL, a blocked/login-walled or
markup-mismatched permalink fetch, network failures/timeouts, download failures, disk
errors. Exit code `0` on full success; non-zero (`1`) if any URL failed or was skipped
as unrecognized. Logging: standard `logging`, default `LOG_LEVEL=INFO`, `--verbose` for
debug detail.

## 12. Security Requirements

Sanitize filenames; prevent path traversal; use HTTPS; never execute downloaded files;
apply sensible timeouts; don't trust external metadata blindly. No credentials exist to
leak.

## 13. Testing Requirements

`pytest`; no test makes a real request to facebook.com, **and no test launches a real
browser** — the same policy extended to cover Playwright. `shared/browser.py`'s Playwright
orchestration (launching a browser, navigating, intercepting real responses) is
deliberately uncovered by the automated suite; only its pure predicate
(`is_media_response`) is unit-tested. The orchestration itself is validated by the project
owner running it against real Facebook, on their own machine, under their own login —
never in CI or by an agent. Cover: config (defaults/overrides/invalid); `shared/scraping`
(success, non-200, redirect-to-login, text-based login wall); `shared/browser`
(`is_media_response` only); Photos & Reels scrapers (media-ID derivation, media-URL
extraction, login-wall propagation); Downloader (image/video download, HTTP/network
failure, filename generation, safe path handling); Manifest (insert/lookup/update,
duplicate detection, resume); CLI (URL classification, mixed photo/reel batches,
`--urls-file`, unrecognized URLs, one failure not aborting the batch, `--force`,
`--verbose`, no-URLs error, browser-fallback invoked only on tier-1 failure, `--headless`
passthrough).

## 14. Dependencies & Constraints

Prefer: Python 3.12+, `httpx`, `pydantic`, `pydantic-settings`, `python-dotenv`, `pytest`,
`ruff`, `playwright`. `pyproject.toml` with a standard build backend; entry point
`python -m facebook_extractor`. `playwright install chromium` is a required one-time setup
step beyond `pip install` (documented in README.md) — pip alone doesn't fetch the browser
binary.

MUST NOT use a web framework, Docker, or other infrastructure not already listed here
without asking first. The Playwright dependency is scoped exactly to §9 SCRAPE-006/§19 —
resolving one media URL at a time under the user's own local login, nothing more. Don't
extend it toward general-purpose browser automation (auto-login flows, scripted
interaction beyond navigate-and-observe, multi-tab/session management) without the same
explicit sign-off this addition itself required.

## 15. Output Structure & Scope

```
downloads/
├── .manifest.db
├── photos/<media_id>.jpg ...
└── reels/<media_id>.mp4 ...
```

No per-Page subdirectory — there's no single Page per run.

**In scope**: URL-list-driven Photo/Reel downloading (any public post the user can supply
a URL for), classification, two-tier resolution (plain HTTP, then a browser under the
user's own local login), downloading, duplicate detection, manifest, resume, CLI, logging,
error handling, tests, docs.
**Out of scope**: bulk Page-level discovery/listing (§9 SCRAPE-002 — confirmed blocked;
tier-2 resolves one URL at a time and does not change this), web UI, any web framework,
cloud deployment/storage, distributed processing, scheduled jobs, CAPTCHA-solving,
detection-evasion techniques beyond "a real browser, logged in as a real person" (fingerprint
spoofing, proxy/UA rotation, request-timing mimicry), storing credentials anywhere but the
browser's own local profile directory (§19).

## 16. Definition of Done

`python -m facebook_extractor <urls...>` accepts one or more Photo/Reel URLs (and/or
`--urls-file`), classifies each, resolves its real media URL (plain HTTP first, browser
fallback second), detects duplicates, downloads into the correct subdirectory, maintains
the manifest, resumes across runs, reports failures per URL without aborting the batch,
prints a final summary that's honest about not being the official API, passes tests and
Ruff, and has complete setup/usage/risk documentation — including the browser fallback's
one-time `playwright install chromium` step and its first-run manual login.

## 17. Claude Code Instructions

Treat this SPEC.md as the source of truth. Prefer simple solutions; avoid unnecessary
abstractions — this project has repeatedly removed modules once they had no remaining
callers (a Page-resolution slice, a Page-URL parser, two model classes, the entire
listing/pagination layer) rather than deprecating them in place; keep applying that
standard. Never widen the boundaries in §19 without the same explicit, informed sign-off
from the project owner — that includes the boundaries §19 still holds even after adding
browser automation (no CAPTCHA-solving, no fingerprint/detection evasion, no bulk listing).
When a scraping pattern breaks against real Facebook markup, the fix is a narrowly-scoped
regex/pattern update with a test fixture capturing the new shape — not a rewrite toward
heavier automation, and not a rebuild of the bulk-listing approach §9 SCRAPE-002 already
confirmed dead. Ask before major architectural changes. If a requirement is ambiguous,
surface the ambiguity before making a major architectural decision.

## 18. Version History

- **v1.x** used the official Meta Graph API. Correct and safe, but couldn't reach Pages
  the user doesn't administer (Photos needed a Page Access Token or Meta's gated Pages
  Public Content Access; Reels had no read endpoint at all, for anyone).
- **v2.0** dropped the Graph API for unofficial bulk scraping of a Page's `/photos` and
  `/videos` listing tabs, achieving "any public Page" in principle. Live testing (§9
  SCRAPE-002) found those listing tabs universally redirect to a login wall — confirmed
  across four Pages of very different size/profile, zero content served in any case.
- **v3.0** dropped bulk Page-level listing entirely. The user supplies specific
  Photo/Reel URLs (found via their own logged-in browsing); the tool resolves and
  downloads each one.
- **v3.1** (this version) added the browser-automation fallback. Live testing of v3.0
  (§9 SCRAPE-003) against one real Reel URL and one real Photo URL found plain HTTP
  resolved *neither* — mobile permalinks hit the same login wall as bulk listing, and
  desktop permalinks returned a JavaScript shell with no media data in the static HTML.
  This was a comprehensive enough dead end (every URL shape, both media types) that the
  project owner explicitly reconsidered the "no login, no browser automation" boundary
  from v2.0/v3.0, with the full technical picture laid out first (§19) — not just "add
  login," but "login plus either browser automation or reverse-engineered internal APIs,"
  with the account-ban and detection risks that implies. The project owner chose browser
  automation with their own login, explicitly accepting those risks.

## 19. Risk Disclosure & Boundaries (read this before touching scraping OR browser code)

This is not a technicality — it's the central trade-off of this project. The history
matters here, because the decision below was made with unusually complete information,
not as a first resort:

1. The Graph API path was shown to structurally not support "any public Page" (v1.x).
2. Bulk listing was shown to be live-blocked, universally (v2.0, §9 SCRAPE-002).
3. Individual permalinks — the fallback v3.0 shrank to — were *also* shown to be
   unreachable via plain HTTP, on every URL shape tested, for both media types (§9
   SCRAPE-003). This wasn't a partial or theoretical gap; it was a complete dead end for
   the only remaining unauthenticated approach.
4. The project owner offered to log in personally to get past this. Before accepting,
   the actual scope of what that requires was laid out explicitly: not just "log in," but
   "log in **and** either run a real browser to execute the page's JavaScript, or
   reverse-engineer Facebook's private, constantly-rotated internal API" — with the
   attendant risks (headless-browser fingerprinting is itself a stronger bot-detection
   signal than a plain HTTP client ever was; reverse-engineered internal APIs need
   ongoing maintenance as Facebook rotates them specifically to break this kind of tool).
5. With that full picture, the project owner chose: real browser automation (not internal
   API reverse-engineering), using their own login, accepting the risks below.

**Accepted risks (not resolved by this spec — owned by the project owner):**
- **Violates Facebook's Terms of Service**, now more directly — automation tied to a real
  logged-in account, not just anonymous requests. Meta has pursued scraping operations
  before, including account-level enforcement (checkpoints, limits, bans).
- **The project owner's own Facebook account may be flagged, limited, or banned** by
  Facebook's automation detection. This is the risk that was specifically discussed and
  accepted (§18 v3.1) — it is not bounded in advance the way an anonymous request simply
  failing was.
- **Fragile by construction**, on both tiers — tier-1 patterns break silently when markup
  changes; tier-2 (browser) breaks if Facebook changes what triggers the media response,
  adds new checkpoint flows, or detects and blocks the automation pattern itself.
- **No documented rate limit** applies on either tier — see SCRAPE-004.

**What was explicitly approved (v3.1):**
- A real browser (Playwright/Chromium), under the project owner's own local Facebook
  login, established manually by them in a visible window — this tool never sees or
  stores a password (§9 SCRAPE-006).
- Observing the media response the page naturally requests while rendering (network
  interception), as an alternative to reverse-engineering Facebook's internal API.
- Headful by default, so a checkpoint/CAPTCHA surfaces for the user to clear manually.

**Hard boundaries that STILL do NOT move without a fresh, explicit conversation with the
project owner** (approving browser automation did not approve these — they were
deliberately kept separate and re-affirmed when browser automation was discussed):
- **No CAPTCHA-solving, automated or otherwise.** A checkpoint/CAPTCHA is the user's to
  clear, in the visible browser, every time (SCRAPE-007) — including when `--headless`
  is set; that flag controls the default case, not this one.
- **No detection-evasion techniques beyond "a real browser, logged in as a real
  person."** No fingerprint spoofing, no user-agent/proxy rotation, no mimicking human
  request timing, no multiple accounts/sessions.
- **No credential storage beyond the browser's own local profile directory**
  (`.browser_profile/`) — no username/password ever passed to or held by this tool's own
  code, no cookies extracted and stored separately, nothing synced anywhere.
- **No enumeration beyond what was explicitly, manually supplied** — no guessing IDs, no
  reverse-engineering Facebook's internal GraphQL/API contracts directly, no rebuilding
  bulk Page listing (browser automation resolves one given URL; it does not turn back
  into a crawler).

If a future requirement would require crossing one of these, the correct action is to
stop and ask — the same way the Graph API's limitations, the bulk-listing login wall, and
then the login/browser-automation boundary itself were each surfaced explicitly, with the
real technical scope laid out, rather than silently worked around or assumed to already
be covered by an earlier, narrower approval.
