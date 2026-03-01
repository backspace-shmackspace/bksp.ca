# Red Team Review (Round 2): Post Composer and Content Management Plan

**Reviewed:** 2026-03-01
**Reviewer:** Critical Reviewer
**Plan:** `plans/dashboard-post-composer.md` (revised)
**Round:** 2 (prior round verdict: FAIL)

---

## Verdict: PASS

All Critical and Major findings from Round 1 have been addressed. No new Critical findings identified. Two new Major findings and several Minor findings are noted below.

---

## Round 1 Finding Resolution

### Finding 1 (Critical): URN ID mismatch between API and XLSX — RESOLVED

The revised plan introduces per-post XLSX import (Section 10), which uses `urn:li:share:{id}` in its "Post URL" field. This is the same URN format returned by the Posts API `x-restli-id` header. The plan now stores the share ID as `linkedin_post_id` for API-published posts and matches against per-post XLSX imports using the same share ID. The plan explicitly acknowledges that aggregate XLSX imports (which use `urn:li:activity:{id}`) will not auto-match API-published posts, and documents per-post XLSX as the recommended linking path. This is a reasonable design that addresses the core concern.

One residual risk remains: the plan assumes (Assumption #9) that the per-post XLSX "Post URL" field always contains `urn:li:share:{id}`. If LinkedIn changes this format, matching will silently fail. However, this is an acceptable assumption given that the alternative (no linking at all) was the Round 1 critical finding.

### Finding 2 (Major): No CSRF protection on publish — RESOLVED

Section 6 now specifies CSRF protection using the same nonce cookie + HMAC pattern as the disconnect endpoint. The publish endpoint validates a `csrf_token` field in the request body, and the compose template includes the CSRF token as a hidden field. Save-as-draft is exempted from CSRF (reasonable, since it has no external side effects). Acceptance criteria #3 explicitly requires CSRF validation.

### Finding 3 (Major): Path traversal protection is fragile — RESOLVED

The draft reader now uses `Path.is_relative_to()` (Python 3.9+) instead of string prefix comparison. This is the correct fix. Test #24 covers path traversal blocking.

### Finding 4 (Major): Member ID race condition — RESOLVED

Section 4 restructures the OAuth callback to fetch the member ID before calling `store_tokens()`, passing both the token response and member ID in a single call. The code sample shows the correct sequence: (1) exchange code, (2) fetch member ID, (3) store both together. This eliminates the window where a token row exists without a member ID.

One note: the existing `oauth_routes.py` callback (line 168) calls `store_tokens(db, token_response)` synchronously. The revised plan calls `get_member_id()` with `await`, which means `exchange_code_for_tokens()` also needs to become async, or it needs to remain sync and run in a thread. The plan's code sample mixes `await exchange_code(code)` (async) with the existing `exchange_code_for_tokens()` (sync, uses `httpx.post` not `httpx.AsyncClient`). This is an implementation detail that will surface during coding, not a design flaw, so I consider the finding resolved.

### Finding 5 (Major): Synchronous httpx blocks event loop — RESOLVED

The Context Alignment section (line 19) and Section 3 (line 276) both confirm all outbound LinkedIn API calls use `httpx.AsyncClient`. The `create_post()` and `get_member_id()` functions are both declared `async` with `httpx.AsyncClient` context managers. Acceptance criteria #18 explicitly requires async API calls.

Note: the existing `exchange_code_for_tokens()` and `refresh_access_token()` in `oauth.py` still use synchronous `httpx.post()`. The plan does not address converting those, but the Round 1 finding acknowledged this as a pre-existing issue.

### Finding 6 (Major): No idempotency on publish — RESOLVED

The plan adds both client-side and server-side dedup: (a) the publish button is disabled after first click with a loading spinner (Section 8, line 802), re-enabled only on error; (b) server-side content hash dedup with a 60-second window (Section 6, lines 630-652). A 409 response is returned for duplicates within the window. Acceptance criteria #5 covers both sides.

### Finding 7 (Minor): Frontmatter not stripped — RESOLVED

Section 5 adds `_strip_frontmatter()` using a regex to remove the leading YAML frontmatter block. The `read_draft_file()` function calls it before returning content.

### Finding 8 (Minor): Orphan draft rows — ACCEPTED

The plan explicitly accepts this as low risk for a single-user app (line 42). Reasonable.

### Finding 9 (Minor): No rate limit backoff — RESOLVED

Section 3 now raises `LinkedInRateLimitError` with a parsed `retry_after_seconds` from the Retry-After header. The UI shows "Rate limited. Try again in X seconds." Acceptance criteria #17 covers this.

### Finding 10 (Minor): `content_format` naming — ACCEPTED

Renaming would break existing API consumers. Reasonable.

### Finding 11 (Minor): Character limit validation — ACCEPTED

The plan validates client-side and surfaces API errors if the limit is wrong. Reasonable.

### Finding 12 (Info): Migration default status — RESOLVED

Line 255 explicitly documents: "Queries filtering for imported posts use `status IS NULL`, not `status = 'imported'`." Acceptance criteria #9 confirms this.

### Finding 13 (Info): Token expiry during publish — ACCEPTED

5-minute buffer is sufficient for a 15-second timeout window.

### Finding 14 (Info): No scope visibility check — RESOLVED

Section 6 (line 688) adds a pre-flight scope check: verifies `w_member_social` is in `OAuthToken.scopes` before calling the API. Returns 403 with a specific re-authorization message. The compose page disables the Publish button when the scope is missing. Acceptance criteria #4 covers this.

### Finding 15 (Info): No rollback strategy — RESOLVED

Lines 1241-1252 document the rollback SQL. Phase 4 starts with a database backup step (line 1299).

---

## New Findings

### 1. Aggregate XLSX import will overwrite API-published post metrics with lower values (Major)

**Severity: Major**

The existing `_upsert_post()` in `ingest.py` (lines 562-577) uses a "higher value wins" strategy for cumulative metrics. This works for aggregate XLSX re-imports where the export date range widens over time, so metrics only grow.

However, the plan introduces a new scenario: a post published via the API will have `linkedin_post_id` set to the share ID (e.g., `7432391508978397184`). The aggregate XLSX export uses activity IDs (different numbers). This means an aggregate XLSX import will _not_ match the API-published post by `linkedin_post_id`. Instead, it may fall through to the date-based fallback match in `_upsert_post()` (lines 547-559: "Fall back to composite key: post_date + title[:100]" and "Fall back to date-only match when title is None").

If a date-based fallback match occurs, the aggregate XLSX import would update the API-published post's metrics with whatever the aggregate export contains, which may be lower than the per-post XLSX data already imported. The "higher value wins" logic would protect against this for most fields, but the newly added fields (`saves`, `sends`, `profile_views`, `followers_gained`, `reposts`) are not present in aggregate exports. The aggregate `_upsert_post()` code does not know about these new fields and would leave them untouched (which is correct, but only because it does not attempt to set them).

The real risk is the date-based fallback match itself: if the user publishes two posts on the same day (one via API, one not), the date-only match (`post_date + title=None`) could incorrectly merge them. The plan's enhanced `_upsert_post()` (Section 9, lines 857-867) only adds the status transition logic; it does not address the false-match scenario.

**Recommendation:** Add a guard in `_upsert_post()`: if an existing post has `status = "published"` or `status = "analytics_linked"` and `linkedin_post_id` is set, skip the date-based fallback match for that post. API-published posts should only match by `linkedin_post_id`, never by date.

---

### 2. The `exchange_code_for_tokens` function is synchronous but the revised callback uses `await` (Major)

**Severity: Major**

The plan's revised OAuth callback (Section 4, line 528) shows:

```python
token_response = await exchange_code(code)
member_id = await get_member_id(token_response["access_token"])
```

But the existing `exchange_code_for_tokens()` in `oauth.py` (line 191) is a synchronous function that uses synchronous `httpx.post()`. It returns a `TokenResponse` dataclass, not a dict (so `token_response["access_token"]` would fail; it should be `token_response.access_token`).

The plan introduces `get_member_id()` as an async function in `linkedin_client.py`. Calling it from the callback requires the callback to be `async def`. The existing callback is already `async def`, so `await get_member_id()` works. But `exchange_code_for_tokens()` is not async, so `await exchange_code(code)` would raise a TypeError at runtime.

The implementer will need to either: (a) make `exchange_code_for_tokens()` async (which touches the refresh flow and the `_refresh_lock` threading.Lock, requiring a switch to asyncio.Lock), or (b) call it without `await` and just use the return value directly. Option (b) is simpler and matches the existing pattern, but the plan's code sample is wrong.

This is a Major finding because the incorrect code sample could lead to either a runtime error (if followed literally with `await`) or an overlooked sync-in-async blocking call (if the implementer removes `await` but does not convert to async). The plan should specify which approach to take.

**Recommendation:** Clarify in the plan that `exchange_code_for_tokens()` remains synchronous (it is called once during the redirect flow, where blocking is acceptable), and the callback calls it without `await`. Only `get_member_id()` is async. Update the code sample to:

```python
token_response = exchange_code_for_tokens(code)
member_id = await get_member_id(token_response.access_token)
store_tokens(db, token_response, member_id=member_id)
```

---

### 3. Per-post XLSX import commits inside `ingest_per_post_xlsx` but the caller also commits (Minor)

**Severity: Minor**

The `ingest_per_post_xlsx()` function (Section 9, line 1066) calls `db.commit()` at the end. But it will presumably be called from the upload endpoint, which follows the `ingest_file()` pattern (line 753-793). That function also calls `session.commit()` after adding the Upload record. If `ingest_per_post_xlsx()` is called within the same session, the inner commit finalizes the transaction before the Upload record is added. If the Upload record insert fails, the post data is already committed and cannot be rolled back.

The existing `load_to_db()` function (line 740) also commits, and `ingest_file()` commits again after adding the Upload. This is a pre-existing pattern, but the plan should be aware that per-post XLSX imports do not have transactional atomicity with the Upload record.

**Recommendation:** Use `db.flush()` instead of `db.commit()` inside `ingest_per_post_xlsx()`, and let the caller handle the commit. This matches better transactional semantics. Low priority since the existing pattern already has this issue.

---

### 4. Batch upload endpoint has no file count limit (Minor)

**Severity: Minor**

The plan adds `POST /api/upload/batch` (Section 9, line 1076) that accepts multiple files. The individual file size limit (50 MB) is enforced by `validate_upload()`, but there is no limit on the number of files in a batch. An extremely large batch (hundreds of files) could consume significant memory and processing time. Given that this is a single-user local app, the risk is low, but a reasonable upper bound (e.g., 50 files) would prevent accidental misuse.

**Recommendation:** Add a file count limit to the batch endpoint (e.g., max 50 files per request).

---

### 5. The `_check_dedup` cache is in-process and resets on restart (Minor)

**Severity: Minor**

The dedup cache (Section 6, lines 632-652) is an in-process `OrderedDict`. If the server restarts between a user's first publish click and the (delayed) second click, the dedup check will not detect the duplicate. This is an accepted limitation for a single-process app, and the client-side button disable provides the primary protection. However, the plan should note this limitation explicitly.

**Recommendation:** Add a comment noting that the dedup cache is ephemeral and does not survive server restarts. The client-side button disable is the primary double-submit guard.

---

### 6. Per-post demographics percentage handling may produce incorrect values (Minor)

**Severity: Minor**

The `_parse_per_post_demographics()` function (lines 955-964) handles percentages in three formats:
- `float` or `int`: stored directly (e.g., `0.31`)
- String containing `<`: stored as `0.005`
- String otherwise: parsed as `float(str.rstrip("%")) / 100`

The third case divides by 100, assuming the value is like "31%". But the first case assumes the value is already a decimal (0.31). If LinkedIn returns `31` as an int (meaning 31%), the first case would store it as `31.0` instead of `0.31`. The plan should verify the actual format in the real XLSX export. If percentages come as whole numbers (31 vs 0.31), all the demographic bars would show 3100%.

**Recommendation:** Verify the actual percentage format in the per-post XLSX export. If it is whole-number percentages (e.g., 31 for 31%), divide by 100 for the `int`/`float` case as well. If it is already decimal (0.31), the current code is correct.

---

### 7. No test for the CSRF token generation on the compose page (Info)

**Severity: Info**

The test plan includes `test_publish_missing_csrf_returns_403` (#10) and tests for the publish flow with CSRF. But there is no test that the compose page route (`GET /dashboard/compose`) actually generates and includes a CSRF token (nonce cookie + hidden field). If the page renders without the CSRF token, the publish button will always fail with 403.

**Recommendation:** Add a test that `GET /dashboard/compose` sets the nonce cookie and includes the CSRF token in the response HTML.

---

### 8. The plan does not specify how `POST /api/upload/batch` handles format auto-detection per file (Info)

**Severity: Info**

The batch upload endpoint processes multiple files, each of which could be either per-post or aggregate format. The plan says "Each file is processed independently" (line 1076) and the `_detect_xlsx_format()` function exists, but the batch endpoint's implementation is not specified. It is unclear whether each file goes through the existing `ingest_file()` pipeline (which calls `parse_linkedin_export()` for aggregate format) or the new `ingest_per_post_xlsx()` directly. The routing logic should be specified.

**Recommendation:** Specify that the batch endpoint opens each workbook, calls `_detect_xlsx_format()`, and routes to either `ingest_file()` (aggregate) or `ingest_per_post_xlsx()` (per-post) accordingly. Return per-file results in the response.

---

### 9. `engagement_rate` is not recalculated after per-post XLSX import (Info)

**Severity: Info**

The `ingest_per_post_xlsx()` function (line 1042) calls `post.recalculate_engagement_rate()` only when creating a new post. When updating an existing post (lines 1015-1024), it updates individual metrics (`reactions`, `impressions`, etc.) but does not call `recalculate_engagement_rate()`. The existing `_upsert_post()` always calls it (line 576). This means a per-post XLSX import that updates an existing post could leave `engagement_rate` stale.

**Recommendation:** Call `post.recalculate_engagement_rate()` after updating metrics on an existing post in `ingest_per_post_xlsx()`.

---

## Summary

The revised plan successfully addresses all 6 Critical and Major findings from Round 1. The URN mismatch (the Round 1 critical) is resolved through the per-post XLSX import design, which uses the same `urn:li:share:{id}` format as the API. CSRF, path traversal, race condition, async httpx, and idempotency are all properly addressed.

Two new Major findings were identified: (1) aggregate XLSX imports could falsely match API-published posts via the date-based fallback, and (2) the code sample for the revised OAuth callback contains sync/async mixing errors. Neither is a Critical issue; both are addressable during implementation with the recommendations above.
