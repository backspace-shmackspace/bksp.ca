# Code Review: linkedin-analytics-dashboard

**Reviewed:** 2026-02-28 (re-review after revision)
**Reviewer:** code-reviewer agent
**Plan:** `plans/linkedin-analytics-dashboard.md`
**Previous review:** 2026-02-28 (initial)

---

## Verdict: PASS

All four Major findings from the initial review are resolved or adequately addressed. No new Critical or Major findings were identified in the revised code.

---

## Previous Findings: Resolution Status

### Finding 1 — Uploaded file never deleted on ingest failure or duplicate (`app/routes/upload.py`)

**Status: RESOLVED**

The `finally: pass` stub is replaced with working cleanup logic. An `ingest_succeeded` boolean (line 114) is set to `True` only on the success path (line 117). The `finally` block (lines 137-146) calls `dest_path.unlink()` when `ingest_succeeded` is `False`, covering `DuplicateFileError`, `IngestError`, and all other exception paths. The size-limit early-exit path (lines 101-102) and the file-save exception path (line 111) both also call `dest_path.unlink(missing_ok=True)` before returning. All failure paths now clean up.

### Finding 2 — `GET /api/export/db` streams a live, potentially corrupt SQLite file (`app/routes/api.py`)

**Status: RESOLVED**

The endpoint no longer returns the live database file directly. It now uses the SQLite Online Backup API (`sqlite3.connect().backup()`, lines 377-383) to produce a consistent point-in-time snapshot written to a UUID-named temporary file alongside the source database (line 375). The snapshot is returned via `FileResponse` with a `BackgroundTask` (lines 393-411) that deletes the snapshot file after the response is fully sent. The WAL-consistency problem from the initial review is addressed correctly.

### Finding 3 — File size limit validated after full write (`app/routes/upload.py`)

**Status: RESOLVED**

The upload handler now reads incoming data in 1 MiB chunks (`_CHUNK_SIZE = 1024 * 1024`, line 20). It accumulates `total_written` per chunk (line 94) and aborts before writing the offending chunk when the running total exceeds `max_bytes` (lines 95-107). The partially-written file is removed immediately (`dest_path.unlink(missing_ok=True)`, line 102) before the error response is returned. The size limit is now enforced at the HTTP boundary as required.

### Finding 4 — `conftest.py` mutates `settings.__dict__` directly (`tests/conftest.py`, `tests/test_routes.py`)

**Status: PARTIALLY ADDRESSED — accepted as-is**

The `__dict__` mutation pattern remains in both `conftest.py` (line 112) and `test_routes.py` (line 77). The revision narrows and documents the approach correctly: only `data_dir` (the underlying stored field) is mutated, and both files now include a comment explaining that `uploads_dir` and `db_path` are `@property` methods deriving from `data_dir` and therefore need no separate override. The previous version also redundantly mutated `uploads_dir`, which was a property and therefore had no effect; that redundant mutation is removed.

The fragility risk from pydantic-settings v2 internals still exists in principle, but the approach is now defensible for a local tool with a single settings singleton. The original value is restored in teardown in both fixtures. Escalating to a `model_copy` + dependency override approach remains the correct long-term fix, but this revision is acceptable for the scope of this project.

---

## Critical Findings

None.

---

## Major Findings

None.

---

## Minor Findings

### 1. Export snapshot written to `db_path.parent`; no explicit permission check (`app/routes/api.py`, line 375)

The snapshot file is created in the same directory as the database (`db_path.parent`). If the application user lacks write permission to that directory at export time (e.g., a misconfigured Docker volume), the `sqlite3.connect()` call raises an `OperationalError` that is caught and re-raised as HTTP 500. The 500 response is correct, but the error message ("Failed to create database snapshot") does not help the operator diagnose a permissions issue. A log line that includes the target path would assist debugging. This is cosmetic for a local tool.

### 2. Unused import in `requirements.txt`: `aiofiles` (carried over from initial review)

`aiofiles` remains in `requirements.txt` and is not imported anywhere in the codebase. It can be removed.

### 3. `_parse_date` does not document `dd/mm/YYYY` ambiguity (carried over from initial review, `app/ingest.py`)

`ingest.py` tries `%m/%d/%Y` before `%d/%m/%Y`. For dates like `01/02/2025` the first matching format wins. A short comment explaining the ordering decision and its tradeoff would prevent future confusion.

### 4. `validate_upload` calls `file_path.stat()` twice (`app/ingest.py`, carried over from initial review)

Two consecutive `file_path.stat()` calls for the zero-size check and the max-size check. Assign `stat_result = file_path.stat()` once and reuse `stat_result.st_size`.

### 5. `.gitignore` does not cover SQLite WAL/SHM sidecar files (carried over from initial review)

`.gitignore` entries `data/uploads/` and `data/linkedin.db` leave `data/linkedin.db-wal` and `data/linkedin.db-shm` unignored. Now that the export endpoint explicitly operates in WAL mode, these sidecar files are more likely to appear. Replace both lines with `data/` to cover the whole directory.

---

## Positives

- **All four Major findings from the initial review are addressed.** The file-cleanup logic, the backup-API export, and the chunked size-limit enforcement are all implemented correctly. The quality of the fixes is high: the cleanup uses a boolean flag rather than checking exception type, the export uses `BackgroundTask` for post-response cleanup rather than a fragile try/finally, and the chunked read aborts before writing the oversized chunk rather than after.

- **Security posture remains solid.** All query parameters mapping to column or category names use `pattern=` allowlists via FastAPI validation. No raw SQL anywhere. File extension validation is in the ingest layer, not trusted from the content-type header.

- **Deduplication is well-implemented.** Three-tier dedup strategy (LinkedIn post ID, date+title composite, date-only fallback) plus SHA256 file-level dedup. The NULL-aware `IS` filter in `_upsert_daily_metric` correctly handles SQLite's NULL != NULL behavior in unique constraints.

- **Test coverage is thorough.** All acceptance criteria from the plan are covered: empty-db behavior, seeded-db behavior, duplicate upload 409, invalid file 400, invalid query params 422, engagement rate calculation, cascade deletes, UPSERT semantics, and full ingest pipeline end-to-end. The shared-connection fixture pattern for in-memory SQLite tests is the correct solution to per-connection isolation.

- **The ingest pipeline is defensively written.** Per-row parse errors accumulate as warnings rather than crashing the import. Missing sheets produce warnings, not errors. Multiple date format variants are tried in order. Column name lookups are case-normalized with fallback aliases.

- **Docker configuration matches the plan.** Bind mount over named volume is correctly justified. The healthcheck uses the specified approach. `start_period: 10s` prevents false-negative health failures during startup.

- **Templates are correct and complete.** All five views from the plan are implemented. Empty-state UX is handled on the dashboard and audience pages. Server-side data is passed to Chart.js via inline JSON using `tojson`, with Jinja2 auto-escaping preventing XSS.
