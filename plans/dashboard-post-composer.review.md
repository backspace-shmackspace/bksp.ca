# Plan Review: Post Composer and Content Management (Round 2)

**Plan reviewed:** `plans/dashboard-post-composer.md`
**Reviewed:** 2026-03-01
**Reviewer:** Librarian
**CLAUDE.md version:** Current (checked `~/bksp.ca/CLAUDE.md`)
**Review type:** Round 2 re-review (Round 1 verdict: PASS, no required edits)

---

## Verdict: PASS

The revised plan incorporates findings from all three review documents (red team, feasibility, Round 1 librarian review). All 15 red team findings and all feasibility concerns are addressed with explicit resolution status in the new "Review Findings Incorporated" section. The plan remains compliant with CLAUDE.md rules, introduces no new conflicts, and is historically aligned with prior plans.

---

## Round 1 Resolution Status

Round 1 returned PASS with no required edits and four optional suggestions. Resolution status:

### 1. Clarify canonical location of `linkedin-api-architect.md` agent -- PARTIALLY ADOPTED

The plan still references `.claude/agents/linkedin-api-architect.md` without specifying which copy is canonical. However, the reference is to the agent's design principles (not to the file itself), so this is non-blocking. The plan's usage is clear enough.

### 2. Clarify URN mismatch risk mitigation timeline -- RESOLVED

The revised plan adds Section 10 ("LinkedIn Post URN Format and ID Matching") which fully resolves the URN mismatch concern. The per-post XLSX export uses `urn:li:share:{id}`, matching the API response format. The plan documents the ID matching strategy for all three import paths (API-published, per-post XLSX, aggregate XLSX) and explicitly states that aggregate XLSX imports will not auto-match API-published posts. This is a clear, well-documented resolution.

### 3. Add `DRAFTS_DIR` to Docker deployment section -- RESOLVED

Section 2 (Configuration) now specifies the Docker volume mount command (`-v ~/bksp/drafts/linkedin:/app/drafts/linkedin`) and states `DRAFTS_DIR` must be set to `/app/drafts/linkedin` in Docker. The rollout plan (Phase 4, step 27) includes "Docker compose rebuild and deploy (include `DRAFTS_DIR` volume mount)." Fully addressed.

### 4. Consider adding `linkedin_member_id` to Settings page -- NOT ADOPTED

The plan does not add member ID display to the Settings page. This was optional and remains non-blocking.

---

## Red Team and Feasibility Findings Resolution

The revised plan adds a "Review Findings Incorporated" subsection under Context Alignment that tracks all findings. Verification of key resolutions:

- **Red team #1 (Critical, URN mismatch):** Resolved via Section 10. Per-post XLSX uses share URN format. The plan correctly acknowledges that aggregate XLSX imports use a different ID space and will not auto-match.
- **Red team #2 (Major, CSRF):** Addressed. Section 6 specifies nonce cookie + HMAC CSRF protection on the publish endpoint, matching the disconnect endpoint pattern. Acceptance criteria #3 codifies this.
- **Red team #3 (Major, path traversal):** Fixed. Section 5 uses `Path.is_relative_to()` (line 611). Acceptance criteria #16 codifies this.
- **Red team #4 (Major, member ID race):** Fixed. Section 4 restructures the callback to fetch member ID before `store_tokens()`.
- **Red team #5 (Major, sync httpx):** Fixed. Section 3 uses `httpx.AsyncClient` with `async with` and `await`. Acceptance criteria #18 codifies this.
- **Red team #6 (Major, idempotency):** Addressed. Section 6 implements both client-side button disable and server-side content hash dedup with 60-second window.
- **Red team #7 (Minor, frontmatter):** Fixed. Section 5 includes `_strip_frontmatter()` function.
- **Red team #9 (Minor, rate limit):** Addressed. Section 3 parses 429 with `Retry-After` header, raises `LinkedInRateLimitError` with `retry_after_seconds`.
- **Red team #14 (Info, scope visibility):** Addressed. Section 6 includes pre-flight scope check for `w_member_social` before calling API.
- **Red team #15 (Info, rollback):** Addressed. Data Migration section includes rollback SQL and notes SQLite 3.35.0+ requirement.
- **Feasibility C2 (endpoint access):** Addressed. Phase 0 in rollout plan tests both `/rest/posts` and `/v2/ugcPosts`. Section 3 includes a payload comparison table for both endpoints.

All resolutions are consistent and traceable.

---

## Conflicts with CLAUDE.md Rules

None identified. Specific checks:

- **Sensitivity protocol (CRITICAL):** Post content stored locally, never shared externally. Composer publishes only to the user's own LinkedIn account. Draft file paths reference local files. No employer-identifiable data involved. Compliant.
- **No em-dashes (BANNED):** Full text searched; zero em-dashes found. Compliant.
- **Voice and style:** Not directly applicable to a technical plan (no published copy is generated). Content pipeline integration is correctly described.
- **Dark theme consistency:** Plan specifies Navy #0a0f1a / card #111827 / accent #3b82f6 palette with Inter + JetBrains Mono fonts. Compliant.
- **Content pipeline integration:** Correctly integrates with `~/bksp/drafts/linkedin/` and the `/mine` to `/repurpose` pipeline documented in CLAUDE.md. Compliant.
- **Ian's professional background (CRITICAL CONTEXT):** Plan makes no claims about Ian's background. No conflicts.
- **Stack consistency:** Stays within FastAPI + SQLAlchemy + SQLite + Jinja2 + Tailwind CDN + Chart.js + Pydantic Settings. httpx already in requirements.txt. No new dependencies. Compliant.
- **Single-user, self-hosted:** Plan maintains single-account design throughout. Compliant.

---

## Context Alignment Section Assessment

The `## Context Alignment` section is substantive and expanded from Round 1. It now includes four subsections:

1. **CLAUDE.md Patterns Followed:** 9 bullet points covering stack, config, theme, sensitivity, em-dashes, single-user design, httpx, migration scripts, and content pipeline. All accurate.
2. **Prior Plans Consulted:** 5 entries with approval status and rationale. The `bksp-social-cma-app.md` characterization as "NOT APPROVED, ABANDONED" is editorially reasonable (noted in Round 1 as an observation, not a conflict).
3. **Review Findings Incorporated:** New subsection tracking all findings from red team, librarian, and feasibility reviews with resolution status for each. This is a strong addition.
4. **Deviations from Established Patterns:** 4 deviations documented with justification (scope expansion, new module, filesystem dependency, per-post XLSX parser). All reasonable.

Assessment: The Context Alignment section is thorough, accurate, and improved from the original version.

---

## Historical Alignment Issues

No contradictions with prior plans.

- **Consistent with `linkedin-analytics-dashboard.md` (APPROVED).** This plan implements the post publishing component of Phase 3. The scope limitation (using `w_member_social` without full Marketing API) is correctly documented.
- **Consistent with `linkedin-oauth-auth.md` (APPROVED).** Builds on the OAuth infrastructure, extends scopes with documented re-authorization requirement.
- **Consistent with `engagement-analytics.md` (APPROVED).** Follows the same migration script pattern (`migrate_002` following `migrate_001`). Same stack, same testing conventions.
- **Consistent with `bksp-social-cma-app.md` abandonment.** Correctly avoids CMA-dependent features. Stays within the `linkedin-analytics` codebase.
- **Context metadata block is present and updated.** `revised_at` timestamp added. `reviews_incorporated` field added listing all three review documents. All metadata values verified accurate.

---

## Required Edits

None.

---

## Optional Suggestions

- **Aggregate XLSX import gap deserves a user-facing note.** Section 10 clearly documents that API-published posts will not auto-match aggregate XLSX imports (different ID spaces). Consider adding a UI indicator on the post detail page when a post was published via the API but only has aggregate XLSX data available: "This post was published via the dashboard. Use a per-post XLSX export for accurate analytics linkage." This helps the user understand why aggregate import did not link.

- **`_extract_activity_id` function name is now misleading.** The function (Section 3, line 355) handles share, ugcPost, and activity URNs but is still named `_extract_activity_id`. Consider renaming to `_extract_urn_id` or `_extract_post_id` since it extracts from share/ugcPost URNs (not just activity URNs). The function name was flagged in the feasibility review (m2) and the regex was expanded, but the name was not updated.

- **Consider a `linkedin_urn_full` column.** The plan stores only the numeric portion of the URN in `linkedin_post_id`. Storing the full URN string (e.g., `urn:li:share:7432391508978397184`) in a separate column would make debugging and future API integrations easier, since the URN type prefix carries semantic information about which API surface created the post.

<!-- Context Metadata
reviewed_at: 2026-03-01T23:30:00Z
claude_md_exists: true
plan_status: DRAFT
verdict: PASS
round: 2
previous_verdict: PASS
reviews_incorporated: dashboard-post-composer.redteam.md, dashboard-post-composer.feasibility.md
-->
