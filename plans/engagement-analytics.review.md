# Plan Review: Engagement Quality Analytics (Re-review)

**Plan:** `plans/engagement-analytics.md`
**Reviewed against:** `CLAUDE.md` (project root)
**Review date:** 2026-02-28
**Review type:** Re-review (previous review: 2026-02-28)

---

## Verdict: FAIL

One of two required edits from the previous review remains unaddressed. See below.

---

## Previous Required Edits Resolution

### 1. Remove stray `</output>` tag (line 584) -- NOT RESOLVED

The plan still ends with a stray `</output>` tag after the context metadata block (now at line 593). This was flagged as a required edit in the initial review and has not been removed.

### 2. Reconcile `recent_plans_consulted` in metadata with body -- RESOLVED

The body's "Prior Plans Consulted" section now includes `plans/bksp-ca-astro-cloudflare-blog.md` with a clear scope-conflict note: "Reviewed for scope conflicts. The blog plan's 'No analytics in v1' non-goal refers to Cloudflare Web Analytics on the blog site, not the LinkedIn analytics dashboard. No conflicts." The metadata block and body are now consistent.

---

## Conflicts

- **None blocking.** The plan does not violate any CLAUDE.md rules.
- **Em-dash ban:** No em-dashes found. Compliant.
- **Sensitivity protocol:** Dashboard is local/self-hosted, cohort labels are user-defined, no employer-identifiable data stored or displayed. Compliant.
- **Professional background rules:** Not directly relevant to a tooling plan. No violations.
- **Content pipeline integration:** Explicitly connects to `/mine` and `/repurpose` pipeline. Suggested cohort topics align with the three content lanes. Compliant.
- **Stack consistency:** Stays within established FastAPI/SQLAlchemy/SQLite/Jinja2/Chart.js/Tailwind CDN stack. No new dependencies. Compliant.

---

## Required Edits

1. **Remove stray `</output>` tag (line 593).** The plan ends with `</output>` after the context metadata block. This is not valid plan content and is a copy-paste artifact. Remove it. (Carried forward from initial review.)

---

## Optional Suggestions

These are non-blocking observations. Several optional suggestions from the initial review were adopted in this revision (noted for completeness):

- **Adopted: `content_format` column naming.** The plan now uses `content_format` throughout instead of `format`, avoiding the Python built-in shadow. Good.

- **Adopted: Weighted score formula rationale.** The `weighted_score` property docstring now explains why comments are weighted 3x ("signal deeper engagement") and shares 4x ("signal advocacy/amplification"). The new "Metric relationship note" paragraph clearly distinguishes `engagement_rate` from `weighted_score`. Good.

- **Adopted: Blog plan in Prior Plans Consulted.** Now included with a scope-conflict analysis. Good.

- **Still relevant: Bulk tagging in Non-Goals.** The risks table mentions "Add a bulk tag feature in a future iteration" but this is not listed under Non-Goals. Consider adding "No bulk tagging UI in this iteration" to Non-Goals so it is formally deferred rather than buried in a risk mitigation note.

- **Still relevant: Post count guard for percentile calculation.** The `_compute_top_10pct_threshold` function returns 0.0 for empty lists but does not guard against very small datasets (1-2 posts). The "Not enough data" message in the risks table should be formalized as a minimum post count (e.g., 10 posts) before the top 10% threshold line is rendered on the chart.
