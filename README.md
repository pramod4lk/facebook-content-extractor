# facebook-content-extractor

A local Python CLI that downloads specific public Facebook Photos and Reels, given their
direct URLs.

Full behavioral spec: [SPEC.md](SPEC.md).

> **This is an unofficial tool, not a Meta Graph API integration**, and it does **not**
> discover a Page's content for you — you supply the exact URLs (found by browsing
> Facebook yourself). Resolution is two-tier: a plain HTTP fetch first; if Facebook serves
> that URL as a JavaScript-only shell (increasingly the norm — see "How it works"), it
> falls back to a real browser logged in with **your own** Facebook session. Read "Risks
> and boundaries" below before using this — it covers real, not hypothetical, trade-offs.

## Requirements

- Python 3.12+
- Your own Facebook account, for the browser fallback (see Setup). This tool never sees
  or stores your password — you log in yourself, once, in a real browser window it opens.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium   # one-time: downloads the browser the fallback tier uses
```

`.env` is entirely optional — both settings have defaults:

| Variable | Required | Default |
|---|---|---|
| `OUTPUT_DIRECTORY` | no | `./downloads` |
| `LOG_LEVEL` | no | `INFO` |

## Usage

Browse Facebook normally, find the Photo or Reel you want, copy its URL, and pass it in —
one at a time or several at once:

```bash
python -m facebook_extractor "https://www.facebook.com/photo/?fbid=123456789"
python -m facebook_extractor "https://www.facebook.com/reel/987654321/" "https://fb.watch/abc123/"
```

**First time the browser fallback is needed**, a visible Chromium window opens to
facebook.com. Log in there yourself, then press Enter in the terminal to continue. That
session is saved locally in `.browser_profile/` (gitignored) and reused on future runs —
you generally only do this once.

For a larger batch, put one URL per line in a text file (`#`-prefixed lines are ignored):

```bash
python -m facebook_extractor --urls-file my_urls.txt
```

Other flags:

```bash
python -m facebook_extractor --force <url>      # re-download even if already in the manifest
python -m facebook_extractor --verbose <url>    # debug-level logging
python -m facebook_extractor --headless <url>   # run the browser fallback invisibly (see risks below)
```

Output:

```
downloads/
├── .manifest.db      # SQLite download manifest (duplicate detection, resume)
├── photos/<media_id>.<ext>
└── reels/<media_id>.<ext>
```

Re-running with overlapping URLs skips already-downloaded media and retries previously
failed media, unless `--force` is passed.

## How it works

For each URL, this tool first tries a plain HTTP GET — the same request an ordinary
logged-out browser would make — and looks for the real media URL already embedded in the
response (`og:image` for Photos, `og:video`/embedded player data for Reels). In practice,
as of this version, that tier resolves **neither** Photos nor Reels reliably: Facebook's
individual permalink pages are now client-rendered shells whose actual media URL is
fetched by JavaScript after the page loads, and mobile-site permalinks redirect to a login
wall outright.

When that happens, it falls back to a real, visible Chromium browser (via Playwright),
using your own locally-saved Facebook login, that actually loads the page and runs its
JavaScript. Rather than trying to decode Facebook's private API, the tool just watches for
the video/image network request the page itself makes while rendering, and downloads
whatever URL that turns out to be.

## Risks and boundaries

**Accepted, not resolved by this tool:**
- **Violates Facebook's Terms of Service** — more directly than a purely anonymous
  scraper would, since the fallback tier is tied to a real logged-in account.
- **Your Facebook account could be flagged, limited, or paused by Facebook's own
  automation detection.** This is the real, specific risk of the browser fallback, not an
  abstract policy statement — weigh it before relying on this for anything that matters.
- **Will break without warning, on both tiers.** Tier 1 breaks when Facebook changes its
  page markup; tier 2 breaks if Facebook changes what triggers the media request, adds a
  new checkpoint flow, or starts detecting the automation itself.
- **No official rate limit exists on either tier**, so a failure is treated as "blocked or
  broken," not something to retry through.

**What this tool will still never do, even to fix breakage** (see SPEC.md §19 for the
full history — the login/browser-automation trade-off above was reached deliberately,
with the full technical picture laid out first, not as a first resort):
- **No CAPTCHA-solving.** If Facebook shows a checkpoint or CAPTCHA in the browser window,
  that's yours to clear by hand — every time, even in `--headless` mode (which will
  effectively just get stuck until you drop the flag and clear it visibly).
- **No detection-evasion beyond "a real browser, logged in as a real person."** No
  fingerprint spoofing, no user-agent/proxy rotation, no mimicking human request timing.
- **No credentials handled by this tool's own code.** Your password never touches it —
  only Facebook's own login page sees it. The resulting session lives only in
  `.browser_profile/` on your machine.
- **No bulk discovery.** The browser resolves one URL you give it; it doesn't turn into a
  crawler of a Page's content.

## Development

```bash
pytest          # run tests (no real requests to facebook.com; no real browser is launched)
ruff check .    # lint
```

`shared/browser.py`'s actual browser automation is deliberately not covered by the
automated test suite (only its pure response-matching logic is) — validating it against
real Facebook, under a real login, only happens when you run the tool yourself.

Project layout follows vertical slice architecture — see [CLAUDE.md](CLAUDE.md) and
SPEC.md §7 (`photos/`, `reels/` slices, each just a `scraper.py`, plus a `shared/`
package for the HTML fetcher, browser fallback, downloader, retry helper, and manifest).
