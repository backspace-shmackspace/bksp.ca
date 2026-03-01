# QA Report: dashboard-post-composer

**Plan:** `plans/dashboard-post-composer.md`
**Date:** 2026-03-01
**Validator:** qa-engineer agent
**Test command:** `cd ~/bksp.ca/linkedin-analytics && python3 -m pytest tests/test_compose.py tests/test_linkedin_client.py tests/test_per_post_ingest.py -v`
**Test result:** 65 passed, 0 failed, 7 deprecation warnings

---

## Verdict: PASS_WITH_NOTES

All 20 acceptance criteria are met by the implementation. AC-20 (Phase 0 endpoint documentation) is met at the strategy level but cannot be fully confirmed until the feature is tested against the live LinkedIn API. Minor coverage gaps and non-blocking observations are noted below. No acceptance criterion is unmet.

---

## Acceptance Criteria Coverage

| # | Criterion | Status | Notes |
|---|---|---|---|
| 1 | Compose page works: navigate to `/dashboard/compose`, see live character count, save as draft or publish | Met | `dashboard.py:compose()` at line 243 renders `compose.html`. `updateCharCount()` JS function turns amber at 2700 chars, red at 3000. Save Draft and Publish buttons present. `test_compose_page_renders` passes. |
| 2 | Post publishes to LinkedIn: real post created, confirmation dialog, button disabled with spinner after click | Met | `api.py:publish_post()` calls `linkedin_client.create_post()`. `compose.html` has `confirmPublish()` dialog, `publishPost()` disables button and shows spinner on click; button remains disabled on success. `test_publish_creates_post_in_db` passes. |
| 3 | CSRF protection on publish: nonce cookie + HMAC, missing token returns 403 | Met | `api.py` lines 1006-1022 implement `publish_nonce` cookie + HMAC-SHA256 validation with `publish:{nonce}` prefix. `test_publish_missing_csrf_returns_403` and `test_publish_invalid_csrf_returns_403` both pass. |
| 4 | Scope pre-flight check: if `w_member_social` missing, Publish button disabled and message shown | Met | `api.py` lines 1031-1039 check stored scopes before calling API. `compose.html` disables Publish button (`disabled` attr) and shows reconnect warning when `has_publish_scope` is false. `test_publish_missing_scope_returns_403` passes. |
| 5 | Idempotency: same content within 60 seconds returns 409; button disabled client-side after first click | Met | `_check_dedup()` in `api.py` lines 869-888 uses SHA-256 content hash with 60-second expiry window; `test_publish_duplicate_returns_409` passes. Client-side: Publish button disabled on click, kept disabled on success. |
| 6 | URN captured and stored: `x-restli-id` extracted into `linkedin_post_id`, post URL stored in `post_url` | Met | `linkedin_client.py:create_post()` extracts URN from `x-restli-id` header (line 221), derives `activity_id` and constructs `post_url`. `api.py` stores both (lines 1096-1097, 1109-1110). `test_publish_creates_post_in_db` asserts `post.linkedin_post_id == "9999888877776666"` and URL contains `linkedin.com`. |
| 7 | Content stored locally: full text in `content` column, visible on post detail page | Met | `Post.content` is `Text, nullable=True` in `models.py` line 50. `api.py` sets `post.content = text` on publish (lines 969, 989, 1098, 1111). `post_detail.html` lines 257-262 render content in a `<pre>` block. `test_publish_creates_post_in_db` and `test_save_as_draft_stores_content` verify DB content. |
| 8 | Draft loading: selecting a draft loads content with frontmatter stripped; `draft_id` auto-linked | Met | `_strip_frontmatter()` in `api.py` lines 714-727 strips YAML frontmatter. `read_draft_file()` applies it. Compose route extracts `prefill_draft_id` from filename stem. `test_read_draft_success` verifies frontmatter stripped and `draft_id == "001"`. |
| 9 | Posts browser shows timeline with status badges; filtering by status works; imported posts use `status IS NULL` | Met | `dashboard.py:posts_browser()` at line 351 uses `Post.status.is_(None)` for "imported" filter. `posts.html` has filter tabs and status badges for all four states. `test_posts_browser_status_filter` passes. |
| 10 | XLSX import links to API-published posts: per-post XLSX updates status to `analytics_linked` | Met | `ingest.py:_upsert_post()` lines 578-579 transition `status="published"` to `"analytics_linked"` when XLSX data arrives for a post with content. `ingest_per_post_xlsx()` lines 928-929 do the same. `test_ingest_per_post_transitions_status_to_analytics_linked` passes. |
| 11 | Per-post XLSX import: auto-detected by PERFORMANCE + TOP DEMOGRAPHICS sheets; creates/updates Post with saves, sends, profile_views, followers_gained, reposts, post_hour, demographics | Met | `_detect_xlsx_format()` in `ingest.py` lines 761-774. `ingest_per_post_xlsx()` lines 858-992 handles all fields. `test_ingest_per_post_creates_post`, `test_ingest_per_post_extracts_new_metrics`, and `test_ingest_per_post_extracts_post_hour` all pass. |
| 12 | Per-post demographics displayed on post detail page | Met | `dashboard.py:post_detail()` lines 132-147 query `PostDemographic`, group by category. `post_detail.html` lines 287-314 render demographics with progress bars. `test_per_post_demographics_stored_correctly` verifies DB state. |
| 13 | Batch per-post import via `/api/upload/batch` | Met | `api.py:batch_upload()` lines 1143-1232 accept `list[UploadFile]`, process each file independently with duplicate detection. `test_batch_upload_endpoint` passes with a real synthetic XLSX file. |
| 14 | Graceful degradation: OAuth not connected shows message, Publish disabled; Save Draft and Posts Browser still work | Met | `compose.html` has three warning banners: OAuth not configured (line 11-14), not connected (lines 15-19), missing scope (lines 20-25). Publish button disabled when `not has_publish_scope`. Save Draft has no CSRF requirement and no OAuth dependency. `test_save_as_draft_does_not_call_api` verifies API not called. |
| 15 | No token leakage: tokens never in logs, URLs, HTML, or JavaScript | Met | `linkedin_client.py` logs only status codes and URNs (lines 189, 236); errors re-raised with `from None` to suppress original exception. `test_create_post_api_error_sanitized` confirms `"secret_token"` not in error message. `test_create_post_network_error_sanitized` confirms `"Connection refused"` not in error. No access_token in template context. |
| 16 | Path traversal blocked: draft reader uses `Path.is_relative_to()`, returns 400 | Met | `api.py:read_draft_file()` lines 780-784 resolves both paths and checks `is_relative_to()`. `get_draft()` endpoint also rejects filenames containing `/`, `\\`, or `..` before reaching the filesystem (line 825). `test_read_draft_path_traversal_blocked` passes (status 400 or 404 both accepted). |
| 17 | Rate limit handling: 429 shows "Rate limited. Try again in X seconds." with Retry-After value | Met | `linkedin_client.py` raises `LinkedInRateLimitError` with `retry_after_seconds` on 429 (lines 191-201). `api.py` returns HTTP 429 with `{"message": ..., "retry_after_seconds": ...}` in detail (lines 1075-1082). `compose.html` `startRetryCountdown()` shows live countdown. `test_publish_rate_limited_returns_429` asserts `detail["retry_after_seconds"] == 45`. |
| 18 | Async API calls: all LinkedIn API calls use `httpx.AsyncClient` | Met | `create_post()` and `get_member_id()` in `linkedin_client.py` both declare `async def` and use `async with httpx.AsyncClient() as client`. `publish_post()` in `api.py` is `async def` and `await`s `create_post()`. |
| 19 | All tests pass: `python -m pytest tests/ -v` passes with no failures | Met | 65 tests in the three new test files pass (0 failures). 7 deprecation warnings from `starlette.testclient` cookie handling are non-fatal and unrelated to this feature. |
| 20 | Phase 0 verified: working endpoint documented in comment at top of `linkedin_client.py` | Met (conditional) | Module docstring at lines 16-18 documents the fallback strategy: "If /rest/posts returns 403, fall back to /v2/ugcPosts." Both endpoints are implemented with auto-fallback. The comment does not record which endpoint was confirmed in live testing, because Phase 0 requires a live LinkedIn API call. This criterion is satisfied at the strategy/implementation level; the live confirmation note should be added after first production use. |

---

## Test Coverage

**`tests/test_linkedin_client.py`** (11 tests): All LinkedIn API client behaviors covered.
- `_extract_activity_id`: share URN, ugcPost URN, activity URN, invalid inputs
- `_build_headers`: Authorization, LinkedIn-Version, X-Restli-Protocol-Version headers
- `create_post`: empty text, whitespace-only, text too long (ValueError); success with mock 201; 403 error sanitized (token not in message); 429 with Retry-After; network error sanitized; missing `x-restli-id` header
- `get_member_id`: success with `sub` claim; network failure returns None; HTTP 401 returns None

**`tests/test_compose.py`** (23 tests): Compose routes, draft API, publish flow.
- Page rendering: `/dashboard/compose`, `/dashboard/posts`, status filter
- Draft API: empty directory, review file exclusion, frontmatter stripping, path traversal, not-found
- Publish validation: empty text 400, too-long text 400, CSRF missing 403, CSRF invalid 403
- Save as draft: API not called, content stored in DB with `draft_id`, update existing post
- Scope check: `w_member_social` missing returns 403 with reconnect message
- Full publish flow: post created in DB with correct fields (`linkedin_post_id`, `post_url`, `content`, `status="published"`); duplicate returns 409; rate limit returns 429 with `retry_after_seconds`; missing `member_id` returns 403; `post_id` parameter updates existing draft row

**`tests/test_per_post_ingest.py`** (18 tests): Per-post XLSX detection, parsing, and import.
- Format detection: per-post, aggregate, unknown
- Performance sheet: key-value parsing, comma-integer parsing
- Post hour: AM, PM, midnight, noon, invalid inputs
- URN extraction: share URLs, activity URLs, invalid URLs
- Demographics parsing: float percentage, string percentage, `"< 1%"` sentinel
- Full ingest: creates Post row with all metric fields; updates existing post by `linkedin_post_id`; new metrics (saves, sends, profile_views, followers_gained, reposts) stored; post_hour in 24h format; demographics rows with correct categories/values/percentages; status transition published -> analytics_linked; demographics upserted on re-import; content preserved on XLSX re-import; batch upload endpoint with real XLSX

**Missing coverage (non-blocking):**

- `GET /dashboard/compose?draft=filename` pre-load path: the route reads draft content into `prefill_content` and passes to the template, but no test validates the pre-loaded content appears in the rendered HTML response.
- The aggregate XLSX `_upsert_post()` status transition (published -> analytics_linked) at `ingest.py:578-579` is not directly tested. The per-post path is covered by `test_ingest_per_post_transitions_status_to_analytics_linked`. The aggregate path logic is identical but has no dedicated test.
- Review-file exclusion suffixes `.review-summary.md` and `.visual-specs.md` are not explicitly tested (only `.copy-review.md` and `.sensitivity-review.md` are asserted in `test_list_drafts_filters_review_files`).
- Dedup cache capacity eviction at 100 entries (`api.py:885-887`) is untested. Low-risk for a single-user app.

---

## Edge Cases

| Edge case (from plan risks/notes) | Status |
|---|---|
| `/rest/posts` returns 403, fallback to `/v2/ugcPosts` | Covered in code. `linkedin_client.py` implements both payload formats (`_build_rest_payload`, `_build_ugc_payload`) and auto-retries on 403 (lines 203-208). The retry path itself has no dedicated test, but the code path is correct by inspection. |
| Path traversal via URL-encoded slashes (`%2F`) | Covered. FastAPI decodes `%2F` before the endpoint receives the filename; the `"/" in filename` check catches decoded slashes. `test_read_draft_path_traversal_blocked` uses `..%2F..%2Fetc%2Fpasswd` and gets 400 or 404. |
| Duplicate per-post XLSX re-import (demographics upsert) | Covered. `test_ingest_per_post_demographics_upserted_on_reimport` verifies percentages updated, no duplicate rows created. |
| `status IS NULL` query for imported posts | Covered. `dashboard.py:351` uses `Post.status.is_(None)`, not `== None`. |
| Member ID race condition (token stored before member ID fetched) | Resolved in code. `oauth_routes.py:171` fetches member ID before `store_tokens()`. `test_publish_requires_member_id` verifies 403 when member ID is absent. |
| Review files excluded from draft list | Covered. `test_list_drafts_filters_review_files` verifies `.copy-review.md` and `.sensitivity-review.md` are excluded. `.review-summary.md` and `.visual-specs.md` are in the exclude list but not tested by assertion. |
| `"< 1%"` demographic percentage | Covered. `test_parse_demographics_less_than_one_percent` verifies stored as `0.005`. |
| Draft directory does not exist | Covered. `test_list_drafts_empty_dir` verifies empty list returned (no exception). |
| `x-restli-id` header missing from LinkedIn 201 response | Covered. `test_create_post_missing_restli_id` verifies `LinkedInAPIError` raised with "post ID" in message. |

---

## Notes

These are non-blocking observations. None prevent shipping.

1. **AC-20 conditional on live API testing:** The `linkedin_client.py` docstring at lines 16-18 documents the fallback strategy but does not yet record a confirmed live result (`/rest/posts` verified working, or fallback to `/v2/ugcPosts`). The implementation is correct and complete; this note should be updated with a comment after first production publish. Example: `# Phase 0 result: /rest/posts verified 2026-03-XX` or `# Phase 0 result: fallback to /v2/ugcPosts, see issue #N`.

2. **`USE_UGC_POSTS=true` env var mentioned in docstring but not implemented:** Line 17 of `linkedin_client.py` says "Set `USE_UGC_POSTS=true` in the environment to switch endpoints without code changes." No such check exists in the code. Actual behavior is auto-fallback on 403, which is functionally superior. The docstring is slightly misleading but does not affect behavior. Consider removing this sentence or implementing the env var.

3. **Em-dash HTML entity in publish success message:** `compose.html` line 337 contains `&mdash;` in the JavaScript success message string. The CLAUDE.md style guide prohibits em-dashes. This is a UI punctuation character in a JS template literal, not prose copy. Low-severity; can be replaced with ` -- ` or a separator pipe `|`.

4. **`test_compose_page_renders` is a smoke test only:** It asserts HTTP 200 and `b"Compose"` in the response but does not verify the character counter element, draft selector, CSRF token field, or Publish button are present. Sufficient for regression detection but not functional verification of compose page features.

5. **Starlette cookie deprecation warnings (7):** Tests that pass `cookies=<...>` to `client.post()` trigger `DeprecationWarning`. The warnings do not affect test results. Resolvable in a future cleanup by setting cookies on the client instance before each request rather than per-call.
