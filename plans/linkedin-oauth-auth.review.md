# Plan Review: LinkedIn OAuth Auth Setup (Round 2)

**Plan:** `plans/linkedin-oauth-auth.md`
**Reviewed against:** `CLAUDE.md` (project root)
**Review date:** 2026-03-01
**Review type:** Round 2 (follow-up to initial review)

---

## Verdict: PASS

Both required edits from round 1 are resolved. No new conflicts found.

---

## Round 1 Required Edits: Resolution Status

1. **"Legal entity blocker is now resolved" claim was ambiguous.** RESOLVED. The Prior Plans Consulted bullet for `linkedin-analytics-dashboard.md` now reads: "The OAuth flow itself does not require Community Management API access; it works with just `openid profile` scopes (auto-granted with 'Share on LinkedIn'). Community Management API approval is still pending and only required by the future data sync plan, not this auth plan." This clearly separates the OAuth auth scope (this plan) from the Community Management API scope (future data sync plan) and avoids any misleading claim about the legal entity blocker being gone.

2. **Metadata listed `bksp-ca-astro-cloudflare-blog.md` but body didn't mention it.** RESOLVED. The body's "Prior Plans Consulted" section now includes: "`plans/bksp-ca-astro-cloudflare-blog.md`: Reviewed for scope conflicts; no overlap with the Astro blog plan." This follows the exact pattern used in `engagement-analytics.md` and reconciles the metadata with the body.

---

## Conflicts

- **Em-dash ban (Voice & Style > BANNED):** Zero em-dashes found. Compliant.
- **Sensitivity protocol (Sensitivity Protocol > CRITICAL):** OAuth tokens encrypted at rest via Fernet. Client secrets in `.env` (gitignored). Exception sanitization prevents `client_secret` leakage in logs or stack traces. No employer-identifiable data. Compliant.
- **Stack consistency (Quick Start, Content Architecture):** Stays within FastAPI + SQLAlchemy + SQLite + Jinja2 + Tailwind CDN + Pydantic Settings. The only new dependency (`cryptography`) is justified in the Deviations section. Compliant.
- **Dark theme / fonts:** Plan specifies existing Navy/card/accent palette and Inter/JetBrains Mono fonts. Compliant.
- **Professional background rules (Ian's Professional Background):** Not directly relevant to a tooling plan. No violations.

---

## Historical Alignment

### Context Alignment Section

Present and substantive. Three subsections: "CLAUDE.md Patterns Followed" (8 bullet points), "Prior Plans Consulted" (4 plans cited with specific justifications), and "Deviations from Established Patterns" (2 deviations with rationale). Well-developed.

### Prior Plan Consistency

- **`plans/linkedin-analytics-dashboard.md` (APPROVED):** The OAuth plan correctly positions itself as implementing Phase 3's OAuth component only. It clearly states that Community Management API scopes are deferred to the future data sync plan, and that the OAuth flow works with just `openid profile` scopes. The Risks table honestly acknowledges that Community Management API rejection is a medium-likelihood risk that blocks the data sync plan, not this auth plan. **No contradiction.**

- **`plans/engagement-analytics.md` (APPROVED):** The OAuth plan follows the same migration conventions. It correctly notes that `create_all()` handles new tables (unlike engagement-analytics which needed a script for new columns on an existing table). The reasoning is sound and explicitly stated. **No contradiction.**

- **`plans/bksp-ca-astro-cloudflare-blog.md` (APPROVED):** Now cited in both the body and metadata. Reviewed for scope conflicts; no overlap. **No contradiction.**

### Context Metadata Block

- `claude_md_exists: true` -- Confirmed.
- `recent_plans_consulted` -- Lists three plans. All exist in `plans/`. All three are now cited in the body.
- `archived_plans_consulted` -- Lists two feasibility plans. Acceptable.
- Metadata is clean (no stray tags or formatting issues).

---

## Required Edits

None.

---

## Optional Suggestions

- **Redirect URI and reverse proxy documentation.** The default `LINKEDIN_REDIRECT_URI` is `http://localhost:8050/oauth/callback`. The plan mentions validating the path at startup and logging a warning for non-localhost hosts, which is good. Consider adding a note in the `.env.example` documentation (rollout step 10) that Proxmox or reverse proxy deployments must update this value and use HTTPS. The `linkedin-analytics-dashboard.md` plan includes Proxmox deployment notes, so this would maintain cross-plan consistency.

- **Token row cleanup on expired refresh token.** Section 8 step 5c sets `needs_reauth` when the refresh token is expired but does not delete the row. The `get_auth_status` function would return `connected: True, needs_reauth: True`. The settings page (Section 5) shows a warning banner when the refresh token expires within 30 days, but does not specify the UI for an already-expired refresh token. Consider documenting whether the status should show "Connected (re-authorization required)" or "Disconnected" in this terminal state.

- **Scope name verification reminder.** Section 3 includes a useful note about verifying Community Management API scope names against Microsoft Learn documentation at implementation time. Consider adding a code comment or TODO marker in the implementation order (rollout step 4) so this verification step is not forgotten when the data sync plan is implemented.
