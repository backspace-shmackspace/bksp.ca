# Code Review: dashboard-post-composer

**Review type:** Revision review (addressing findings from prior review)
**Prior verdict:** REVISION_NEEDED (2 Major findings: missing tests)

---

## Verdict: PASS

---

## Critical Findings

None.

---

## Major Findings

None.

The two previously missing tests are now present and correct:

### Previously Major 1: `test_publish_requires_member_id` — RESOLVED

Added at `linkedin-analytics/tests/test_compose.py` lines 426-445.

The test seeds an OAuthToken via `_seed_oauth_token`, then sets `token_row.linkedin_member_id = None` and commits. It constructs a valid CSRF token, sends a POST to `/api/posts/publish`, and asserts a 403 response containing `"reconnect"` in the detail.

The implementation at `api.py` lines 1042-1049 raises `HTTPException(status_code=403, detail="LinkedIn member ID not available. Please reconnect in Settings to refresh your connection.")`. The string `"reconnect"` is present and the assertion matches.

Both `app.config.settings.token_encryption_key` and `app.routes.api.settings.token_encryption_key` are monkeypatched to `_TEST_KEY`, which ensures the CSRF check passes before reaching the member ID check. The test exercises the correct code path. **Test runs and passes.**

### Previously Major 2: `test_publish_updates_existing_draft` — RESOLVED

Added at `linkedin-analytics/tests/test_compose.py` lines 448-501.

The test creates a `Post` with `status="draft"`, then calls `POST /api/posts/publish` with `post_id=existing_id` and a valid CSRF token. It asserts:
- The response `id` equals the existing post's ID (no new row created by the response)
- `Post.count() == 1` (no new row in DB)
- The existing row's `status` is `"published"`, `content` is updated, and `linkedin_post_id` is set

The implementation at `api.py` lines 1092-1104 handles the `post_id` branch: it fetches the existing post, updates all fields including `status = "published"`, and commits without inserting a new row. The test logic is correct and directly exercises the specified plan requirement ("POST with `post_id` of an existing draft, verify the draft row is updated, not a new row created"). **Test runs and passes.**

Confirmed: full test suite for `test_compose.py` is 23/23 passing.

---

## Minor Findings

The following minor findings carry forward from the prior review. None have changed in severity.

### M1. `_strip_frontmatter` regex does not handle Windows line endings

`api.py` lines 720-726. The pattern `r"\A---\s*\n.*?\n---\s*\n"` requires `\n`, not `\r\n`. Draft files edited on Windows would not have frontmatter stripped. The existing test uses `\n` only and would not catch this regression.

### M2. `demo_count` undercounts on re-import in `ingest_per_post_xlsx`

`ingest.py` lines 971-983. `demo_count` is only incremented on insert, not on update. The return value `{"demographics_imported": demo_count}` is 0 on re-import even when rows are updated. Cosmetic only; the upsert itself is correct.

### M3. `posts.html` sort URL construction uses an unusual regex trick

`posts.html` line 41. The `.replace(/^/, '?')` pattern works but is harder to read than a ternary or prepending `'?'` directly. Not a correctness issue.

### M4. `test_publish_requires_oauth_connection` docstring is slightly misleading

`test_compose.py` line 193-199. The test name implies it tests the OAuth-required behaviour, but it actually tests that CSRF fails first (403 because CSRF is invalid, not because there are no tokens). The test is correct; the docstring is the issue.

### M5. `compose.html` uses `bg-navy-700` — verify this class is defined in Tailwind config

`compose.html` line 157. If `navy-700` is not defined in the Tailwind CDN config or a custom plugin, this class has no effect and the dialog background will be transparent. Requires manual verification against the deployed Tailwind config.

### M6. Patching `app.routes.api.settings` vs the function-local `_settings` re-import

In `api.py` lines 1015-1018, the publish endpoint does `from app.config import settings as _settings` inside the function body. Monkeypatching `app.routes.api.settings` does not affect this local re-import. Tests correctly work around this by also patching `app.config.settings.token_encryption_key` (which mutates the singleton object directly), but the dual-patch pattern is fragile. If a future refactor changes the import structure, the CSRF tests could silently start failing. This is a pre-existing issue, not introduced in this revision.

---

## Positives

All positives from the prior review carry forward. The revision is clean:

1. Both new tests follow the established patterns in the file exactly: `monkeypatch` for settings, `_seed_oauth_token` for token setup, `_make_publish_csrf` for CSRF token construction, and `patch` context managers for mocking the LinkedIn client.

2. `test_publish_updates_existing_draft` includes the correct post-condition check (`post_count == 1`) to verify no spurious row was created, which is the core correctness assertion required by the plan.

3. `test_publish_requires_member_id` correctly targets the specific code path (token exists but member ID is missing) rather than conflating it with the "no token at all" case tested by `test_publish_requires_oauth_connection`. The distinction is meaningful and correctly exercised.

4. No existing tests were broken by the addition. Full suite: 23/23 passing.
