# Feasibility Review: LinkedIn Analytics Dashboard (Re-Review)

**Plan:** `plans/linkedin-analytics-dashboard.md`
**Reviewed:** 2026-02-28
**Reviewer:** Technical Feasibility Review (re-review)
**Previous review:** 2026-02-28 (initial)

---

## Verdict: PASS

The revised plan has addressed all four previous major concerns. The architecture is sound, the Phase 0 gate is well-structured, and the implementation is appropriately scoped for a single-user home lab tool. Remaining items are minor and can be handled during implementation.

---

## Previous Concerns: Resolution Status

### M1. LinkedIn XLS export format is unverified against the schema
**Status: RESOLVED**

The revised plan now:
- Marks the schema as "PROVISIONAL" with explicit warnings (lines 237-239).
- Adds a mandatory Phase 0 gate that blocks all implementation until a real export is downloaded and inspected (lines 349-361).
- States that "Phase 1 cannot begin until Phase 0 is complete and this plan is updated with verified format details."
- Commits to finalizing sheet names, column headers, data types, date formats, and edge cases (merged cells, empty rows) from real data.

The concern is properly mitigated. The schema is no longer treated as ground truth; it is a provisional starting point that will be validated.

### M2. openpyxl vs xlrd library choice
**Status: RESOLVED**

The revised plan now:
- Lists both `openpyxl` and `xlrd` in the tech stack table (line 162): "openpyxl reads `.xlsx`, xlrd reads legacy `.xls`."
- Includes both in `requirements.txt` (line 481).
- Phase 0 step 8 explicitly requires choosing the correct library or using both with auto-detection (line 358).
- Implementation order step 1 says "pin dependencies (include both `openpyxl` and `xlrd`; remove whichever is unnecessary after Phase 0)" (line 544).
- Implementation order step 4 specifies "XLS/XLSX parser with format auto-detection" (line 548).

Both libraries are available, and the plan defers the final choice to Phase 0 with auto-detection as the default strategy. This is the correct approach.

### M3. Deduplication strategy for overlapping date ranges
**Status: RESOLVED**

The revised plan now includes a dedicated "Post Deduplication Strategy" section (lines 217-225) with five layers:
1. File-level dedup via SHA256 hash (prevents exact re-import).
2. Record-level dedup using a composite key of `post_date` + `title` (first 100 chars) with UPSERT semantics: higher value wins for cumulative metrics, engagement rate is recalculated on every upsert.
3. `linkedin_post_id` used as primary key when available, with fallback to composite key.
4. Daily metrics deduped on `(post_id, metric_date)` unique constraint with UPSERT.
5. Follower/demographic snapshots deduped on their respective unique constraints with UPSERT.

The strategy explicitly handles the overlapping export scenario (Jan-Mar export followed by Feb-Apr export). The "higher value wins" rule for cumulative metrics is a pragmatic choice. The plan also commits to validating this against real data in Phase 0.

### M4. curl missing in Docker healthcheck
**Status: RESOLVED**

The revised `docker-compose.yml` (lines 603-604) now uses a Python-based healthcheck:
```yaml
test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8050/health')"]
```
This avoids the `curl` dependency entirely by using Python's stdlib, which is guaranteed to be present in the `python:3.12-slim` image.

---

## New Concerns

### Critical

None.

### Major

None.

### Minor

**m1. Title-based composite key is fragile for dedup.**
The composite key `post_date + title (first 100 chars)` works for most cases, but LinkedIn posts do not have titles. The "title" field is described as "first ~100 chars of post text." Two posts on the same date with identical opening text (e.g., reposting a corrected version) would collide. This is an unlikely edge case for a personal dashboard, and the plan already commits to revisiting the dedup key after Phase 0 if the real export provides a better identifier. No action needed now, but worth noting during Phase 0 validation.

**m2. "Higher value wins" UPSERT may mask data corrections.**
If LinkedIn retroactively corrects metrics downward (e.g., removing bot engagement), the "higher value wins" rule would preserve the inflated number. For a personal analytics tool this is a minor concern, but the ingestion logic should log when an existing value is being skipped due to this rule so the user can spot anomalies.

**m3. No explicit error handling for concurrent uploads.**
SQLite has limited write concurrency. If two browser tabs upload files simultaneously, the second write could hit a database lock. FastAPI's async nature makes this plausible even for a single user. The plan does not address this.

*Recommendation:* Use SQLAlchemy's `with session.begin()` pattern with a retry on `OperationalError` (database locked), or serialize uploads with an asyncio lock. This is a minor implementation detail, not a design flaw.

**m4. Alembic still not in the dependency list.**
The previous review recommended adding Alembic for future schema migrations. The revised plan still uses `create_all()` only. This is acceptable for Phase 1 but will create friction in Phase 2/3 when schema changes require ALTER TABLE on an existing SQLite database.

*Recommendation:* Add `alembic` to `requirements.txt` and run `alembic init` as part of Phase 1 setup, even if no migrations are written yet. This costs minutes now and saves hours later.

**m5. Upload validation (size limits, MIME type) still not specified.**
The previous review's M3 concern about upload validation was partially addressed (the upload endpoint exists with validation feedback mentioned in the UI description at line 213), but no `MAX_UPLOAD_SIZE` or content-type check is specified in the plan. LinkedIn exports are small (typically under 1MB), so a 10MB limit would be reasonable.

*Recommendation:* Add a `MAX_UPLOAD_SIZE` setting to `config.py` (default 10MB) and validate file extension (.xls, .xlsx, .csv) before parsing.

**m6. Test coverage does not include the UPSERT/dedup path.**
The test plan (lines 417-439) lists "Deduplicate: uploading the same file twice does not create duplicate records" but does not test the overlapping export scenario (two different files with overlapping date ranges producing correct merged data). This is the most nuanced part of the ingestion logic and deserves explicit test coverage.

*Recommendation:* Add a test case: upload file A (Jan-Mar), upload file B (Feb-Apr), verify that February data reflects the higher of the two values and no duplicate records exist.

---

## Summary

The revised plan has meaningfully addressed all four major concerns from the initial review. The Phase 0 gate is the single most important addition: it prevents building against an assumed export format and forces verification before any code is written. The dedup strategy is now explicit and well-reasoned. The Docker healthcheck is fixed. The library choice is deferred correctly.

The remaining minor items (Alembic, upload validation, UPSERT edge cases, overlapping-export test coverage) are implementation-level details that can be handled during Phase 1 development without plan revisions.

**Recommendation: Proceed to Phase 0 (export format verification).**
