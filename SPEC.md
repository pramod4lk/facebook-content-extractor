Facebook Page Photos & Reels Extractor
Specification Version: 1.1
Status: Draft — reviewed, pending Phase 2 API feasibility check (see §23, §29)
Target Runtime: Python 3.12+
Application Type: Local CLI application
Primary API: Meta Graph API

1. Purpose
Build a Python CLI application that accepts a Facebook Page URL through environment configuration, retrieves the Page's available Photos and Reels, and downloads the available media into an organized local directory.

The application is intended to run locally and does not require a web server.

The primary command is:

python -m facebook_extractor

The Facebook Page URL and all sensitive configuration must be provided through .env.

2. Core Workflow
The application workflow is:

.env
 │
 ├── FACEBOOK_PAGE_URL
 ├── META_ACCESS_TOKEN
 ├── META_GRAPH_API_VERSION
 ├── OUTPUT_DIRECTORY
 └── LOG_LEVEL
        │
        ▼
Configuration Loader
        │
        ▼
Configuration Validation
        │
        ▼
Facebook URL Validation
        │
        ▼
Resolve Facebook Page
        │
        ▼
Retrieve Media
        │
        ├───────────────┐
        ▼               ▼
     Photos           Reels
        │               │
        └───────┬───────┘
                ▼
        Duplicate Check
                │
                ▼
           Media Downloader
                │
                ▼
          Local File System
                │
                ▼
        Update Download Manifest
                │
                ▼
          Extraction Summary

3. Primary User Experience
The user should configure .env:

FACEBOOK_PAGE_URL=https://www.facebook.com/examplepage
META_ACCESS_TOKEN=
META_GRAPH_API_VERSION=vXX.X
OUTPUT_DIRECTORY=./downloads
LOG_LEVEL=INFO

Then execute:

python -m facebook_extractor

No Facebook Page URL should be required as a command-line argument.

4. Functional Requirements
FR-001 — Load Configuration
The application MUST load configuration from .env.

Required variables:

FACEBOOK_PAGE_URL=
META_ACCESS_TOKEN=
META_GRAPH_API_VERSION=

Optional variables:

OUTPUT_DIRECTORY=./downloads
LOG_LEVEL=INFO

The application MUST validate required configuration before making any API requests.

FR-002 — Facebook Page URL
The Facebook Page URL MUST be read from:

FACEBOOK_PAGE_URL=

Supported examples include:

https://www.facebook.com/examplepage
https://facebook.com/examplepage
https://www.facebook.com/examplepage/

The application MUST normalize the URL before processing.

Query parameters that do not affect Page identification should be safely ignored.

Invalid URLs MUST produce a clear configuration error.

FR-003 — Resolve Facebook Page
The application MUST resolve the configured Facebook Page URL into a Page identity using supported Meta functionality.

The implementation MUST NOT assume that a Page URL automatically maps to a usable Page ID.

The resolution process must account for:

Authentication
API permissions
API version
Page availability
API limitations
If Page resolution is not possible through the official API under the configured credentials, the application MUST report the limitation clearly.

FR-004 — Extract Photos
The application MUST attempt to retrieve Photos associated with the Facebook Page using the supported Meta Graph API functionality.

For each available Photo, retrieve appropriate metadata where permitted.

Potential metadata includes:

id
page_id
caption
width
height
created_at
permalink
media URL
download URL

The implementation MUST NOT assume that all fields are available.

The extractor MUST handle missing fields gracefully.

FR-005 — Extract Reels
The application MUST attempt to retrieve Reels associated with the Facebook Page using supported Meta Graph API functionality.

Potential metadata includes:

id
page_id
caption
duration
width
height
created_at
permalink
media URL
download URL

The implementation MUST NOT assume that all fields are available.

If Meta does not expose downloadable Reel media for the configured credentials/API version, the application MUST clearly report that limitation.

FR-006 — API Pagination
The application MUST correctly handle Meta API pagination.

The application MUST continue requesting subsequent pages until:

No additional results exist, OR
The configured --limit has been reached (applied independently per media type — see CLI-004).
The implementation MUST NOT assume that a single API request returns all media.

FR-007 — Download Photos
Available Photos with valid downloadable URLs MUST be downloaded into:

<OUTPUT_DIRECTORY>/<page_name>/photos/

Example:

downloads/
└── Example Page/
    └── photos/
        ├── 123456789.jpg
        └── 123456790.jpg

FR-008 — Download Reels
Available Reels with valid downloadable URLs MUST be downloaded into:

<OUTPUT_DIRECTORY>/<page_name>/reels/

Example:

downloads/
└── Example Page/
    └── reels/
        ├── 987654321.mp4
        └── 987654322.mp4

FR-009 — Deterministic Filenames
The preferred filename format is:

<facebook_media_id>.<extension>

Examples:

123456789.jpg
123456790.jpg
987654321.mp4

Media IDs SHOULD be used as the primary identifier because they provide deterministic filenames and simplify duplicate detection.

If a media ID cannot be used, a deterministic safe fallback MUST be generated.

The file extension MUST be derived in this order: (1) the HTTP response's Content-Type header, (2) the extension present in the source/download URL, (3) a default of `.jpg` for Photos or `.mp4` for Reels if neither is determinable.

FR-010 — Safe Filenames
The application MUST sanitize filenames.

It MUST prevent:

Path traversal
Directory traversal
Invalid filesystem characters
Unexpected directory creation
Excessively long filenames
Captions MUST NOT be directly used as filenames without sanitization.

FR-011 — Duplicate Detection
The application MUST avoid downloading the same media repeatedly.

The primary duplicate identifier is:

Facebook Media ID

If a media file already exists and is known to have been successfully downloaded, the application SHOULD skip it.

Default behavior:

Existing media → SKIP

FR-012 — Force Download
The CLI MUST support:

--force

When specified, existing media files MAY be downloaded again.

Example:

python -m facebook_extractor --force

FR-013 — Download Manifest
The application MUST maintain a lightweight download manifest.

The manifest MUST be implemented using SQLite (a single local `.db` file), for transactional writes and safe resumption after interruption.

The manifest MUST track at least:

media_id
page_id
media_type
source_url
local_filename
download_status
downloaded_at

Possible statuses:

pending
downloaded
failed
skipped

The manifest MUST allow the application to determine whether media has already been downloaded.

FR-014 — Resumable Extraction
If an extraction is interrupted, running the application again SHOULD resume without unnecessarily downloading previously completed media.

Previously downloaded media SHOULD be skipped.

Failed media SHOULD be retried on subsequent runs unless explicitly configured otherwise.

5. CLI Requirements
CLI-001 — Default Execution
The primary command MUST be:

python -m facebook_extractor

The Facebook Page URL MUST come from .env.

CLI-002 — Photos Only
Support:

python -m facebook_extractor --photos

This should extract only Photos.

CLI-003 — Reels Only
Support:

python -m facebook_extractor --reels

This should extract only Reels.

CLI-004 — Limit
Support:

python -m facebook_extractor --limit 50

The limit applies independently per media type: `--limit 50` means up to 50 Photos AND up to 50 Reels, not a combined total of 50. When `--photos` or `--reels` restricts the run to one type, the limit applies only to that type's fetch loop.

It MUST NOT incorrectly reset the limit for every pagination request within a single media type's fetch loop.

CLI-005 — Force
Support:

python -m facebook_extractor --force

This allows existing media to be downloaded again.

CLI-006 — Verbose Logging
Support:

python -m facebook_extractor --verbose

This should increase terminal logging detail.

6. CLI Output
The application SHOULD provide clear terminal output.

Example:

Facebook Media Extractor
========================

Page: Example Page
URL: https://www.facebook.com/examplepage

Fetching photos...
Found: 42

Fetching reels...
Found: 18

Downloading photos...
[####################] 42/42

Downloading reels...
[####################] 18/18

Extraction complete.

Photos
------
Found:      42
Downloaded: 40
Skipped:     2
Failed:      0

Reels
-----
Found:      18
Downloaded: 18
Skipped:     0
Failed:      0

Output:
downloads/Example Page/

The application MUST NOT display access tokens or other secrets.

7. Configuration Requirements
CFG-001 — Environment File
The project MUST use .env.

Example:

FACEBOOK_PAGE_URL=https://www.facebook.com/examplepage
META_ACCESS_TOKEN=
META_GRAPH_API_VERSION=vXX.X
OUTPUT_DIRECTORY=./downloads
LOG_LEVEL=INFO

CFG-002 — .env.example
The repository MUST contain:

.env.example

Example:

FACEBOOK_PAGE_URL=https://www.facebook.com/examplepage
META_ACCESS_TOKEN=
META_GRAPH_API_VERSION=vXX.X
OUTPUT_DIRECTORY=./downloads
LOG_LEVEL=INFO

No real credentials may appear in .env.example.

CFG-003 — .gitignore
The repository MUST ignore:

.env
.env.*
!.env.example

downloads/

*.db
*.sqlite
*.sqlite3

__pycache__/
*.py[cod]

.pytest_cache/
.ruff_cache/

.venv/
venv/

CFG-004 — Secret Protection
Sensitive configuration MUST NOT be:

Hard-coded
Logged
Printed
Stored unnecessarily
Committed to Git
Included in exception messages
The configuration implementation SHOULD prevent accidental secret exposure through object representations.

8. Meta Graph API Requirements
API-001 — Official API
The application SHOULD use the official Meta Graph API.

The implementation MUST NOT bypass:

Authentication
Permissions
CAPTCHAs
Rate limits
Access controls
Other Meta technical restrictions
API-002 — API Version
The Graph API version MUST be configurable:

META_GRAPH_API_VERSION=

Do not hard-code the version throughout the application.

API-003 — Access Token
The access token MUST come from:

META_ACCESS_TOKEN=

The token MUST NOT be committed or logged.

API-004 — API Client
All Meta API communication MUST go through a dedicated API client.

Do not place raw HTTP requests throughout the application.

The client SHOULD support:

GET requests
Query parameters
Authentication
Pagination
Timeouts
Error handling
Retry behavior
Rate-limit handling
Logging
Sequential execution — one request at a time; concurrent/parallel requests are out of scope for this version
API-005 — API Feasibility
Before implementation, Claude Code MUST verify the current Meta API documentation and determine:

How Page URLs can be resolved.
How Page Photos can be retrieved.
How Page Reels can be retrieved.
Which permissions are required.
What access token type is required.
Whether media download URLs are available.
Whether those URLs can be downloaded.
What restrictions apply to public Pages.
What API version should be used.
What relevant API changes/deprecations exist.
Claude Code MUST NOT guess API behavior.

9. Architecture
The project uses **vertical slice architecture**: code is grouped by feature (page resolution, photos, reels), not by technical layer. Each slice owns its own service logic, data models, and tests. A small `shared/` package holds only what is genuinely identical across slices (the HTTP client, URL parsing, the downloader, and the manifest) — nothing is extracted into `shared/` speculatively.

The preferred structure is:

facebook-media-extractor/
│
├── src/
│   └── facebook_extractor/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── config.py
│       │
│       ├── shared/
│       │   ├── __init__.py
│       │   ├── http_client.py       # Meta Graph API client: auth, pagination, timeouts, retries, rate-limit handling
│       │   ├── url_parser.py        # Facebook Page URL validation/normalization
│       │   ├── downloader.py        # streaming file download + filename sanitization
│       │   └── manifest.py          # SQLite-backed download manifest
│       │
│       ├── page_resolution/
│       │   ├── __init__.py
│       │   ├── service.py           # resolves a Page URL to a Page identity via http_client
│       │   └── models.py            # Page model
│       │
│       ├── photos/
│       │   ├── __init__.py
│       │   ├── service.py           # Photo API calls, pagination, response normalization
│       │   └── models.py            # Photo model
│       │
│       └── reels/
│           ├── __init__.py
│           ├── service.py           # Reel API calls, pagination, response normalization
│           └── models.py            # Reel model
│
├── tests/
│   ├── test_config.py
│   ├── test_cli.py
│   ├── shared/
│   │   ├── test_http_client.py
│   │   ├── test_url_parser.py
│   │   ├── test_downloader.py
│   │   └── test_manifest.py
│   ├── page_resolution/
│   │   └── test_service.py
│   ├── photos/
│   │   └── test_service.py
│   └── reels/
│       └── test_service.py
│
├── downloads/
├── .env.example
├── .gitignore
├── SPEC.md
├── README.md
└── pyproject.toml

Claude Code MAY modify the structure when there is a clear architectural reason, but MUST preserve the vertical-slice grouping (feature-owned service + models, shared/ only for genuinely cross-slice code).

10. Separation of Responsibilities

Shared components (used by more than one slice):

Configuration
Responsible for:

.env
Environment variables
Validation
Typed configuration

HTTP Client (shared/http_client.py)
Responsible for:

HTTP communication with the Meta Graph API
Authentication
Pagination
Timeouts
Retry behavior
Rate-limit handling
API-level error handling

URL Parser (shared/url_parser.py)
Responsible for:

Facebook URL validation
URL normalization
Page identifier extraction where possible

Downloader (shared/downloader.py)
Responsible for:

HTTP media downloads
Streaming
Filename sanitization and extension derivation
File creation
Download errors
File validation

Manifest (shared/manifest.py)
Responsible for:

Download tracking (SQLite)
Duplicate detection
Download status
Resume behavior

Feature slices (each owns its own service logic and models; no slice depends on another slice's internals):

Page Resolution
Responsible for:

Page resolution via the HTTP client
Page metadata / Page model

Photos
Responsible for:

Photo API operations via the HTTP client
Photo response normalization
Photo model

Reels
Responsible for:

Reel API operations via the HTTP client
Reel response normalization
Reel model

CLI
Responsible for:

User interaction
CLI arguments
Orchestrating slices + shared components in sequence
Progress display
Final summary
Business logic MUST NOT be placed directly inside CLI argument handlers.

11. Data Models
Page
A Page model SHOULD contain:

id
name
username
url

Only include fields available through the API.

Media
A generic Media model SHOULD contain:

id
page_id
media_type
source_url
download_url
filename
mime_type
created_at
downloaded_at

Photo
Photo-specific information MAY include:

width
height
caption
permalink

Reel
Reel-specific information MAY include:

duration
width
height
caption
permalink

All external API fields MUST be treated as potentially optional.

12. Downloader Requirements
The downloader MUST:

Stream large files.
Avoid loading entire videos into memory.
Use HTTPS.
Apply a default request timeout of 30 seconds.
Handle HTTP errors.
Handle network failures.
Create directories automatically.
Support duplicate detection.
Report failures.
Write files safely.
Download items sequentially, one at a time — concurrent/parallel downloads are out of scope for this version.
A failure downloading one item MUST NOT automatically terminate the entire extraction.

13. Retry Requirements
Retry transient failures where appropriate.

Examples:

Network connection failures
Temporary HTTP 5xx errors
Temporary rate-limit responses
Use exponential backoff where appropriate: a maximum of 3 attempts per request, starting at a 1 second delay and doubling (1s, 2s, 4s). Honor a `Retry-After` response header when present instead of the computed backoff.

Do not retry permanent failures indefinitely.

Do not retry:

Invalid credentials
Missing permissions
Invalid Page IDs
Invalid requests
unless the specific error indicates a transient condition.

14. Error Handling
The application MUST gracefully handle:

Missing .env
Missing required configuration
Invalid Facebook Page URL
Page resolution failure
Invalid access token
Expired token
Missing permissions
Meta API errors
Rate limiting
Pagination failures
Network failures
Timeouts
Missing media URLs
Invalid media URLs
Unsupported media
Download failures
Disk errors
Errors should be actionable and understandable.

Example:

Configuration error:

FACEBOOK_PAGE_URL is missing from .env.

Please configure a Facebook Page URL before running the extractor.

Do not display secret values.

Exit code convention: `0` on full success; a non-zero exit code (e.g. `1`) if the run ends with a configuration error, a Page resolution failure, or any failed downloads.

15. Logging
Use Python's standard logging system.

Default:

LOG_LEVEL=INFO

Verbose mode may override this.

Useful logging events include:

Startup
Configuration validation
Page resolution
API operations
Pagination
Media discovery
Download progress
Duplicate detection
Retry attempts
Download failures
Completion summary
Never log:

META_ACCESS_TOKEN

or any other sensitive credential.

16. Security Requirements
The application MUST:

Keep secrets in .env.
Ignore .env in Git.
Validate external URLs.
Sanitize filenames.
Prevent path traversal.
Use HTTPS.
Avoid secret leakage.
Avoid executing downloaded files.
Apply sensible network timeouts.
Avoid uncontrolled downloads.
Avoid trusting external metadata blindly.
17. Testing Requirements
Use pytest.

No unit test should make a real Meta API request.

External HTTP calls MUST be mocked.

Tests MUST cover:

Configuration
.env loading
Required variables
Missing variables
Invalid configuration
Secret protection
URL Parser
Valid Page URL
Invalid URL
Trailing slash
Query parameters
Normalization
API Client
Successful API response
API errors
Authentication errors
Pagination
Retry behavior
Page Service
Successful Page resolution
Page not found
API failure
Photo Service
Successful extraction
Pagination
Missing fields
Empty response
Reel Service
Successful extraction
Pagination
Missing fields
Empty response
Downloader
Successful image download
Successful video download
HTTP failure
Network failure
Duplicate file
Filename generation
Safe path handling
Manifest
Insert
Lookup
Update
Download status
Duplicate detection
Resume behavior
CLI
Default execution
--photos
--reels
--limit
--force
--verbose
18. Dependencies
Prefer:

Python 3.12+
httpx
pydantic
pydantic-settings
python-dotenv
pytest
ruff

Additional dependencies MAY be introduced if there is a clear benefit.

Avoid unnecessary dependencies.

Use `pyproject.toml` with a standard build backend (e.g. hatchling or setuptools). The application is invoked as `python -m facebook_extractor`; no separate console-script entry point is required.

19. No Web Framework
The application MUST NOT use:

Flask
FastAPI
Django
The application is a local CLI.

The internal architecture SHOULD be sufficiently separated that a web API could be added in the future without rewriting the extraction logic.

However, building that API is explicitly out of scope.

20. No Unnecessary Infrastructure
Do not introduce:

Docker
Redis
Celery
RabbitMQ
Kubernetes
PostgreSQL
Cloud storage
Message queues
unless a future requirement specifically requires them.

The first version should remain a simple local application.

21. Output Structure
The expected structure is:

downloads/
└── <page_name>/
    ├── photos/
    │   ├── <media_id>.jpg
    │   └── ...
    │
    └── reels/
        ├── <media_id>.mp4
        └── ...

The page name MUST be safely sanitized before being used as a directory name.

22. Scope
In Scope
Facebook Page URL from .env
Meta API configuration
Page resolution
Page Photos
Page Reels
API pagination
Media metadata
Media downloading
Duplicate detection
Download manifest
Resume behavior
CLI
Logging
Error handling
Tests
Documentation
Out of Scope
Web UI
Flask
FastAPI
Django
Authentication UI
Meta OAuth web flow
Cloud deployment
Cloud storage
Distributed processing
Scheduled jobs
Automatic token renewal
Scraping that bypasses Meta access controls
23. Development Process
Claude Code MUST follow this development process.

Phase 1 — Repository Inspection
Before changing files:

Inspect the repository.
Identify existing source code.
Identify existing dependencies.
Identify existing tests.
Identify existing configuration.
Preserve useful existing code where possible.
Phase 2 — API Feasibility
Before implementing the extractor, investigate current official Meta documentation.

Determine:

Page URL resolution
Page Photos API
Page Reels API
Downloadable media URLs
Permissions
Access-token requirements
Pagination
API version
Current limitations
Do not implement functionality based on assumptions.

Phase 3 — Architecture Proposal
Provide:

Repository assessment
API feasibility assessment
Recommended architecture
Directory structure
Data models
API endpoints
Permissions
Downloader design
Manifest design
Testing strategy
Risks and limitations
Implementation plan
Phase 4 — Approval
After completing Phases 1–3:

STOP.

Wait for explicit user approval before implementing substantial code.

Do not silently proceed.

24. Incremental Implementation
After approval, implement the project in milestones.

Recommended order:

Milestone 1
Project setup + configuration

Milestone 2
Facebook URL parser

Milestone 3
Meta API client

Milestone 4
Page resolution

Milestone 5
Photo extraction

Milestone 6
Reel extraction

Milestone 7
Media downloader

Milestone 8
Manifest + duplicate handling

Milestone 9
CLI + progress reporting

Milestone 10
Testing + documentation + cleanup

Claude Code MAY adjust the order if technically necessary.

25. Quality Gate
After every major milestone, Claude Code MUST:

Run tests.
Run Ruff.
Verify imports.
Check error handling.
Check secret handling.
Check filesystem safety.
Fix discovered issues.
Summarize changes.
Identify the next milestone.
Do not move forward with known failing tests unless the failure is explicitly explained.

26. Definition of Done
The project is complete when:

python -m facebook_extractor

can:

Load .env.
Validate configuration.
Read FACEBOOK_PAGE_URL.
Authenticate using the configured Meta credentials.
Resolve the Facebook Page.
Retrieve available Photos.
Retrieve available Reels.
Handle pagination.
Normalize media metadata.
Detect previously downloaded media.
Download available Photos.
Download available Reels.
Store files in the correct directories.
Maintain the download manifest.
Resume interrupted extraction.
Report failures without unnecessarily terminating the entire job.
Display a final summary.
Avoid leaking credentials.
Pass automated tests.
Pass Ruff.
Have complete setup and usage documentation.
Expected result:

downloads/
└── Example Page/
    ├── photos/
    │   ├── 123456789.jpg
    │   ├── 123456790.jpg
    │   └── ...
    │
    └── reels/
        ├── 987654321.mp4
        ├── 987654322.mp4
        └── ...

27. Important API Limitation
The application MUST only download media that is legitimately exposed to the authenticated application through the available Meta API functionality.

The existence of a publicly viewable Facebook Page does NOT by itself guarantee that its Photos or Reels are available through the API.

If Meta prevents access to a particular Page, media type, metadata field, or download URL, the application MUST clearly report that limitation rather than attempting to circumvent it.

28. Claude Code Instructions
Treat this SPEC.md as the source of truth for the project.

When implementing:

Follow this specification.
Prefer simple solutions.
Avoid unnecessary abstractions.
Do not introduce frameworks without justification.
Do not hard-code secrets.
Do not hard-code the Facebook Page URL.
Do not hard-code the API version.
Do not bypass Meta restrictions.
Do not silently change requirements.
Ask before making major architectural changes.
If a requirement conflicts with current Meta API capabilities, prioritize the actual API behavior and clearly explain the limitation.

If a requirement is ambiguous, identify the ambiguity before making a major architectural decision.

29. First Action
When Claude Code is first started in this repository, it MUST NOT immediately implement the application.

Its first action should be:

1. Inspect the repository.
2. Read SPEC.md.
3. Analyze current Meta API feasibility.
4. Identify the exact API endpoints and permissions required.
5. Produce an architecture proposal.
6. Produce an implementation plan.
7. Identify risks and limitations.
8. STOP and wait for approval.

Only after explicit approval should implementation begin.