# QA Report: linkedin-analytics-dashboard

**Validated against:** `plans/linkedin-analytics-dashboard.md`
**Validation date:** 2026-02-28
**Revision scope:** Post-code-review revision (4 Major findings resolved)

---

## Verdict: PASS_WITH_NOTES

All 10 acceptance criteria are met. Tests pass (79/79). Two non-blocking observations are noted.

---

## Acceptance Criteria Coverage

| # | Criterion | Status | Notes |
|---|---|---|---|
| 1 | `docker compose up` starts with zero config beyond `.env` | Met | `docker-compose.yml` uses `env_file: .env` and `${APP_PORT:-8050}` default. `.env.example` is present. `init_db()` runs in the FastAPI lifespan on startup, creating the DB and directory tree automatically. No manual setup steps required beyond copying `.env.example` to `.env`. |
| 2 | Dashboard at `http://localhost:8050` with dark theme | Met | Port 8050 bound in `docker-compose.yml` and `Dockerfile`. `base.html` uses Tailwind CDN with `bg-navy` body class (`#0a0f1a`), Inter + JetBrains Mono fonts from Google CDN, and a navy/card/accent color palette throughout. Dark theme is the only theme; no light mode toggle exists. |
| 3 | XLS upload works and data appears on dashboard | Met | `POST /upload` in `upload.py` saves the file in chunks, calls `ingest_file()`, and redirects to `/dashboard` on success (HTTP 303). `ingest.py` supports `.xlsx` (openpyxl), `.xls` (xlrd), and `.csv`. `test_upload_valid_xlsx` passes: uploads the synthetic fixture, asserts HTTP 303, and the dashboard route renders with the ingested data. |
| 4 | Post-level metrics displayed per post | Met | `Post` model stores impressions, members_reached, reactions, comments, shares, clicks, and engagement_rate. `dashboard.html` renders a recent-posts table via `_partials/post_table.html`. `/dashboard/posts/{id}` renders a full post detail page. `/api/posts` and `/api/posts/{id}` expose all fields as JSON. `test_get_single_post_found` and `test_list_posts_with_data` both pass. |
| 5 | Time series charts with selectable ranges | Met | `dashboard.html` header renders 7d / 30d / 90d period buttons linking to `/dashboard?days={n}`. The impressions chart has per-metric selector buttons (impressions, reactions, comments, shares) backed by `GET /api/metrics/timeseries?metric={m}&days={n}`. `test_timeseries_with_data` asserts the API returns data with `labels` and `values` arrays. |
| 6 | Duplicate uploads detected and rejected | Met | `ingest_file()` computes SHA256 of the file and checks the `uploads` table for a matching `file_hash` before parsing. Raises `DuplicateFileError`, which `upload.py` catches and returns as HTTP 409. `test_upload_duplicate_file_returns_409` passes. `test_duplicate_file_raises` in `test_ingest.py` passes. |
| 7 | Data persists across restarts (bind mount) | Met | `docker-compose.yml` uses `./data:/app/data` as a bind mount (not a named Docker volume). `init_db()` calls `settings.data_dir.mkdir(parents=True, exist_ok=True)` before `create_all()`, so the directory is created on both first run and all subsequent runs. The SQLite file lives at a stable, predictable host path. |
| 8 | All tests pass | Met | **79/79 tests pass.** Command run: `.venv/bin/python -m pytest tests/ -v --tb=short`. Covers 27 ingestion tests, 21 model tests, and 31 route tests. 124 deprecation warnings are emitted by third-party libraries (pytest-asyncio, FastAPI/Starlette) against Python 3.14 but do not affect test outcomes or production behavior. |
| 9 | Runs on macOS and Linux Docker | Met | `Dockerfile` uses `python:3.12-slim` (Debian-based Linux image). No platform-specific instructions, no macOS-only tooling. `docker-compose.yml` uses standard `build:` syntax compatible with Docker Desktop (macOS) and Docker Engine (Linux/Proxmox). SQLite bind mount works identically on both platforms. |
| 10 | No LinkedIn credentials required | Met | No OAuth flow, no API keys, no LinkedIn SDK. Data ingestion is entirely via manual file upload. `config.py` exposes `app_port`, `data_dir`, `log_level`, and `max_upload_size_mb` only. No credential fields exist anywhere in the codebase. |

---

## Test Coverage

**`tests/test_ingest.py` (27 tests)**
- `TestComputeFileHash`: SHA256 correctness, determinism across files (3 tests)
- `TestValidateUpload`: valid .xlsx, file not found, empty file, unsupported extension, .csv allowed (5 tests)
- `TestParseLinkedinExport`: full parse, required fields present, engagement rate calculation, missing DISCOVERY sheet warns without crash, missing FOLLOWERS sheet warns without crash, malformed rows skipped, empty file raises, unsupported extension raises, CSV accepted, title truncation to 100 chars (10 tests)
- `TestLoadToDb`: posts loaded, UPSERT higher-value-wins, UPSERT does not overwrite higher with lower, full export round-trip, follower snapshots, demographic snapshots (6 tests)
- `TestIngestFile`: successful ingest, duplicate raises `DuplicateFileError`, Upload record created with correct fields (3 tests)

**`tests/test_models.py` (21 tests)**
- `TestPostModel`: create minimal, create full, engagement rate calculation, zero-impressions edge case, linkedin_post_id unique constraint, query, repr (7 tests)
- `TestDailyMetricModel`: create, unique constraint with non-null post_id, multiple NULL post_ids allowed (SQLite NULL != NULL behavior documented and tested), cascade delete from Post, repr (5 tests)
- `TestFollowerSnapshotModel`: create, unique date constraint, query with fixture, repr (4 tests)
- `TestDemographicSnapshotModel`: create, unique constraint, query with fixture, repr (4 tests)
- `TestUploadModel`: create, unique hash constraint, repr (3 tests)

**`tests/test_routes.py` (31 tests)**
- `TestDashboardPages`: root redirect to `/dashboard`, dashboard empty DB, dashboard with data, post detail 404, post detail found, audience empty, audience with data (7 tests)
- `TestUploadRoutes`: form renders, valid .xlsx upload returns 303, duplicate returns 409, invalid extension returns 400, empty file returns 400 (5 tests)
- `TestHealthEndpoint`: `/health` returns 200 with `{"status": "ok"}` (1 test)
- `TestMetricsSummary`: empty DB returns zero values with correct keys, with data returns positive values (2 tests)
- `TestMetricsTimeseries`: empty DB, with data, invalid metric name rejected (422) (3 tests)
- `TestPostsApi`: empty list, list with data, sorting by impressions desc verified in order, single post 404, single post found with `daily_metrics` field present, invalid sort field rejected (422) (6 tests)
- `TestDemographicsApi`: empty DB, with data, invalid category rejected (422) (3 tests)
- `TestFollowersTrendApi`: empty DB, with data asserts exactly 30 labels and 30 total_follower entries (2 tests)

**Missing test coverage (non-blocking):**
- `GET /api/export/db` has no automated test. The endpoint is implemented correctly (SQLite Online Backup API, `BackgroundTask` cleanup) but is not exercised by the test suite. The plan's written test coverage section does not list this endpoint explicitly.
- `max_upload_size_mb` chunked-read enforcement in `upload.py` has no test. Would require generating a file larger than 50 MB.
- `days` parameter boundary values (`ge=1`, `le=365`) on timeseries and followers endpoints are validated by FastAPI but not tested with out-of-range inputs.

---

## Edge Cases (from plan risk section)

| Risk | Coverage |
|---|---|
| LinkedIn changes export format | Covered. `_parse_engagement_sheet` and `_parse_discovery_sheet` try multiple column name variants (e.g. `POST DATE`, `DATE`, `PUBLISHED`, `POST PUBLISHED DATE`). Missing sheets emit warnings and do not crash. Two explicit tests cover this pattern. |
| LinkedIn removes manual export | Not applicable to code. No mitigation possible in the implementation. |
| XLS parsing edge cases | Covered. `test_malformed_data_rows_skipped` verifies rows with unparseable dates are skipped. `_safe_int` and `_safe_float` return defaults on `ValueError`, `TypeError`, or pandas NA. Each row in `load_to_db` is individually wrapped in `try/except` with per-row warning logging. |
| SQLite concurrency | Accepted as N/A (single user). WAL mode is enabled via PRAGMA in `database.py`'s `_set_sqlite_pragmas` connection listener, which improves read concurrency without adding operational complexity. |
| Docker networking on Proxmox | Not applicable to code. Documented in the plan. |
| Scope creep into API integration | No LinkedIn API code exists. |
| Docker volume loss / data recovery | Bind mount in `docker-compose.yml` (not a named volume). `/api/export/db` produces a consistent SQLite snapshot via `sqlite3.connect().backup()`. The snapshot file is cleaned up after download via `starlette.background.BackgroundTask`. |
| Screenshots exposing employer content | Fixture data uses generic cybersecurity topic titles (e.g. "The commitment-without-execution loop in enterprise security"). No employer-identifiable content in any fixture or seed script. |

---

## Notes

**Note 1: No automated test for `/api/export/db`.**
The DB export endpoint is a plan requirement (listed explicitly in API endpoints and SQLite Backup Strategy sections) and is correctly implemented in `api.py` (lines 352-411). It uses the SQLite Online Backup API to produce a point-in-time consistent snapshot, which is the correct approach for WAL-mode databases. However, no test in `test_routes.py` exercises this path. Recommend adding two tests: one asserting HTTP 200 with `application/octet-stream` content type when the DB file exists, and one asserting HTTP 404 when it does not. This is non-blocking because the plan's explicit test coverage list does not enumerate this endpoint.

**Note 2: Python 3.14 deprecation warnings in test output.**
The test run emits 124 `DeprecationWarning` messages from `pytest-asyncio` (`asyncio.get_event_loop_policy` deprecated in 3.14) and FastAPI/Starlette (`asyncio.iscoroutinefunction` deprecated in 3.14). These are upstream library issues and do not affect test outcomes. The production Docker container targets Python 3.12-slim (per `Dockerfile`), which does not emit these warnings. No action required for the implementation.

**Note 3: `.env` file must be created before first `docker compose up`.**
`docker-compose.yml` declares `env_file: .env`. If `.env` does not exist Docker Compose will exit with an error. The plan states "zero config beyond `.env`", which correctly implies the user must copy `.env.example` to `.env` as the one required setup step. The `.env.example` contains sensible defaults and requires no edits for a standard local run. Criterion 1 is met as written. This constraint should be the first step in any README quickstart section.
