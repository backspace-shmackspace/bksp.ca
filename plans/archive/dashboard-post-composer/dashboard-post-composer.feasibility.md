# Feasibility Review: Post Composer and Content Management (Round 2)

**Plan reviewed:** `plans/dashboard-post-composer.md` (revised 2026-03-01)
**Reviewed:** 2026-03-01
**Reviewer:** Feasibility Reviewer
**Round:** 2 (prior: Round 1 PASS with 2 Critical, 5 Major, 7 Minor)

---

## Verdict: PASS

The revised plan addresses all Critical and Major concerns from Round 1 and the red team review. The URN mismatch resolution via per-post XLSX export is sound, and the security improvements (CSRF, path traversal, scope check, idempotency) are well-designed. Two new minor concerns were identified during this review, but nothing blocks implementation.

---

## Round 1 Resolution Status

### Critical Concerns

#### C1. URN ID mismatch between API response and XLSX export (RESOLVED)

**Round 1 finding:** The Posts API returns `urn:li:share:{id}` while aggregate XLSX exports use `urn:li:activity:{id}` with different numeric IDs. Auto-linking would silently fail.

**Resolution:** The revised plan introduces per-post XLSX imports (Section 10), which use `urn:li:share:{id}` in the "Post URL" field. This is the same URN format returned by the Posts API. The plan correctly documents that aggregate XLSX imports (which use `urn:li:activity:{id}`) will not auto-match API-published posts, and recommends per-post XLSX as the primary linkage path. This is a pragmatic solution that avoids the need for a dual-column or URN mapping scheme.

**Verified in plan:** Section 10 (lines 1078-1098), Assumption #9 (line 102), `_extract_urn_from_url()` (line 933-939), `ingest_per_post_xlsx()` (line 973-1073).

**Status: Fully resolved.** The plan is explicit that aggregate XLSX will not match API-published posts. This is an acceptable trade-off documented in the risks table.

#### C2. `/rest/posts` endpoint may require Marketing API access (RESOLVED)

**Round 1 finding:** The `/rest/posts` endpoint may return 403 with only the "Share on LinkedIn" product's `w_member_social` scope.

**Resolution:** The revised plan adds Phase 0 (lines 1258-1264) as a manual verification step before implementation. It documents both the `/rest/posts` and `/v2/ugcPosts` endpoint payload formats in a comparison table (Section 3, lines 499-507) and specifies that the implementation should support both endpoints with a config flag. The callback comment in the code documents which endpoint was verified.

**Verified in plan:** Phase 0 rollout (lines 1258-1264), endpoint comparison table (lines 499-507), `_POSTS_URL` and `_UGCPOSTS_URL` constants (lines 310-311), Assumption #3 (line 96).

**Status: Fully resolved.** Phase 0 eliminates the risk of building against an inaccessible endpoint.

### Major Concerns

#### M1. Path traversal check has symlink bypass (RESOLVED)

**Round 1 finding:** The `startswith` string check could be bypassed with sibling directories sharing a prefix.

**Resolution:** The revised plan uses `Path.is_relative_to()` (Python 3.9+) instead of the fragile `startswith` check.

**Verified in plan:** `read_draft_file()` (line 611), Review Findings section (line 37, 57).

**Status: Fully resolved.**

#### M2. No CSRF protection on publish endpoint (RESOLVED)

**Round 1 finding:** The publish endpoint had no CSRF protection despite being a higher-stakes action than disconnect.

**Resolution:** The revised plan specifies nonce cookie + HMAC token validation on the publish endpoint, matching the existing disconnect endpoint pattern. CSRF is required for publish but not for save-as-draft (which only writes locally).

**Verified in plan:** Architecture overview (line 115), Section 6 endpoint spec (lines 622-623, 669, 687-688), Acceptance criteria #3 (line 1411).

**Status: Fully resolved.**

#### M3. Rate limits not documented (RESOLVED)

**Round 1 finding:** The plan did not document concrete LinkedIn rate limits or handle 429 responses distinctly.

**Resolution:** The revised plan documents the 150 requests/member/day and 100,000 requests/app/day limits (line 704). A dedicated `LinkedInRateLimitError` exception class with `retry_after_seconds` is defined (lines 322-326). The `create_post()` function parses the `Retry-After` header on 429 responses (lines 426-432). The UI shows "Rate limited. Try again in X seconds." (line 803).

**Verified in plan:** `LinkedInRateLimitError` class (lines 322-326), 429 handling in `create_post()` (lines 426-432), rate limit docs (line 704), UI behavior (line 803), test case #5 (line 1339).

**Status: Fully resolved.**

#### M4. No pre-flight scope check before API call (RESOLVED)

**Round 1 finding:** If a user authorized before the scope change, their token lacks `w_member_social` and the API call would fail with a generic 403.

**Resolution:** The revised plan adds a pre-flight scope check that verifies `w_member_social` is in `OAuthToken.scopes` before calling the LinkedIn API. Returns 403 with a clear re-authorization message (line 688). The compose page disables the Publish button when the scope is missing (line 804).

**Verified in plan:** Endpoint spec step 4 (line 688), compose template behavior (line 804), test case #11 (line 1362), Acceptance criteria #4 (line 1412).

**Status: Fully resolved.**

#### M5. Draft-to-publish flow creates duplicate rows (RESOLVED)

**Round 1 finding:** Publishing a saved draft would create a second Post row instead of updating the existing draft row.

**Resolution:** The revised plan adds an optional `post_id` parameter to the publish endpoint (line 666). When provided, the endpoint updates the existing draft row (changing status from "draft" to "published") instead of creating a new row (line 693).

**Verified in plan:** Request body spec (line 666), endpoint logic step 9 (line 693), test case #14 (line 1365).

**Status: Fully resolved.**

### Minor Concerns (Round 1)

| ID | Concern | Status |
|---|---|---|
| m1 | `Path.home()` in Docker | **Resolved.** Docker note added (lines 268, 272). `DRAFTS_DIR` must be set explicitly. |
| m2 | `_extract_activity_id` missing `urn:li:activity` format | **Resolved.** Regex now handles all three URN types (line 363). |
| m3 | No test for migration script | **Not addressed.** Accepted risk; migration is idempotent and simple. Consistent with prior precedent (same gap in `migrate_001`). |
| m4 | Content truncation behavior unspecified | **Resolved.** Truncation specified as `content[:200] + "..." if len(content) > 200 else content` (line 1284). |
| m5 | Template estimate under-scoped | **Resolved.** JavaScript functions documented with event flow and error handling (lines 808-813). |
| m6 | LinkedIn API version may be sunset | **Not addressed.** Accepted risk; version `202601` should be valid until early 2027. Risk table entry unchanged (line 1316). |
| m7 | No idempotency protection on publish | **Resolved.** Client-side button disable (line 802) and server-side 60-second content hash dedup (lines 630-652). |

---

## New Concerns (Round 2)

### Minor Concerns

#### m1. `exchange_code_for_tokens` is synchronous but callback restructuring calls async `get_member_id`

The revised plan restructures the OAuth callback (Section 4, lines 521-537) to call `get_member_id()` (an async function using `httpx.AsyncClient`) immediately after `exchange_code_for_tokens()`. However, `exchange_code_for_tokens()` itself is synchronous (uses `httpx.post()` without async, as seen in `oauth.py` lines 214-216). The callback route is an `async def` FastAPI handler, so calling the synchronous `exchange_code_for_tokens()` blocks the event loop.

This is not a new problem introduced by this plan (it exists today), but the plan adds a second HTTP call (`get_member_id`) in the same callback, extending the blocking window. The `get_member_id` function is correctly async, but the preceding `exchange_code_for_tokens` call is not.

**Recommendation:** Consider converting `exchange_code_for_tokens()` to async (using `httpx.AsyncClient`) as part of the callback restructuring work. This would be consistent with the plan's own principle that "all outbound API calls are async to avoid blocking the event loop" (line 19). If converting is out of scope, add a code comment noting that `exchange_code_for_tokens` is a known synchronous call in an async context.

#### m2. Aggregate XLSX import may overwrite per-post XLSX metrics with lower values

When a post is first imported via per-post XLSX (which captures saves, sends, profile_views, followers_gained, reposts), and then the same post appears in a later aggregate XLSX import, the existing `_upsert_post` function (in `ingest.py`, lines 562-577) uses "higher value wins" logic for `reactions`, `comments`, `shares`, etc. However, the aggregate import sets `reactions = engagements` (line 329) because LinkedIn's aggregate TOP POSTS sheet lumps all engagements together. If the per-post XLSX previously set `reactions` to the true reactions count (lower than total engagements), the aggregate import would overwrite it with the higher but less precise "engagements" value.

The plan's `ingest_per_post_xlsx` function (lines 1015-1024) also uses unconditional `setattr` for metrics, which would overwrite even if the existing value is higher. This differs from the aggregate import's "higher value wins" pattern.

**Recommendation:** Make `ingest_per_post_xlsx` use the same "higher value wins" pattern as `_upsert_post` for cumulative metrics. Consider adding a `source` or `last_import_type` column to Post so the display logic can indicate which import provided the most recent data.

#### m3. `_publish_dedup_cache` does not survive process restarts

The in-memory dedup cache (lines 632-652) is an `OrderedDict` that lives in the process. If uvicorn restarts within the 60-second window, the cache is lost and a duplicate publish could succeed. This is extremely unlikely for a single-user app, but worth noting.

**Recommendation:** Accept this risk. The client-side button disable is the primary dedup mechanism. The server-side cache is a defense-in-depth layer. Document this limitation in a code comment.

#### m4. Batch upload endpoint (`POST /api/upload/batch`) lacks detail

The batch upload endpoint is mentioned (line 1076, 1142) but not specified with the same detail as other endpoints. Missing: request format (multipart/form-data with multiple files?), per-file error handling behavior (does one failure stop all?), response format (list of results?), maximum file count, and whether the existing `Upload` dedup check (file hash) applies to each file individually.

**Recommendation:** Add endpoint specification detail matching the level of `POST /api/posts/publish`. At minimum: request format, per-file error isolation (the plan says "partial failures do not block other files" but the response format should include per-file status), and maximum batch size.

---

## LinkedIn API Verification (Round 2)

All API assumptions from Round 1 remain confirmed. The revised plan's additions are consistent with the documented API behavior:

1. **Per-post XLSX `urn:li:share` format:** Confirmed by the plan's sample data (line 1087). The per-post XLSX export's "Post URL" field contains the share URN, which matches the Posts API `x-restli-id` response header format.
2. **`/v2/ugcPosts` fallback payload:** The comparison table (lines 499-506) correctly documents the payload differences between `/rest/posts` and `/v2/ugcPosts`. The `specificContent.com.linkedin.ugc.ShareContent.shareCommentary.text` path for the legacy endpoint is accurate.
3. **Async `httpx.AsyncClient` for API calls:** The `create_post()` and `get_member_id()` functions correctly use `async with httpx.AsyncClient()` context managers, avoiding connection leaks.

---

## Summary

The revised plan thoroughly addresses all 7 Critical and Major concerns from Round 1, plus all 15 findings from the red team review. The per-post XLSX import is a well-designed addition that resolves the URN mismatch problem and adds valuable new metrics (saves, sends, profile views, followers gained) and per-post demographics.

The 4 new minor concerns identified in Round 2 are implementation-time items that do not affect the plan's viability. The most notable (m2, metric overwrite ordering) should be addressed during implementation but does not require a plan revision.

**Recommended next steps:**

1. Proceed with Phase 0 (manual endpoint verification) to confirm whether `/rest/posts` or `/v2/ugcPosts` is the correct endpoint.
2. Begin implementation in the order specified (Phase 1 through Phase 4).
3. Address m1 (async `exchange_code_for_tokens`) opportunistically during the callback restructuring.
4. Address m2 (metric overwrite semantics) during the `ingest_per_post_xlsx` implementation.
5. Specify the batch upload endpoint (m4) before implementing Phase 2.
