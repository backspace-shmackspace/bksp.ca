# Feasibility Review: Engagement Quality Analytics (Re-review)

**Plan reviewed:** `plans/engagement-analytics.md`
**Reviewed:** 2026-02-28
**Reviewer:** Feasibility Reviewer
**Previous review:** 2026-02-28 (initial)

---

## Verdict: PASS

All three Major concerns from the initial review have been resolved. The revised plan is ready for implementation.

---

## Previous Major Concerns: Resolution Status

### M1. `format` column name shadows Python built-in -- RESOLVED

The revised plan uses `content_format` as both the Python attribute name and the database column name throughout. Specific evidence:

- Model definition (line 76): `content_format: str | None = Column("content_format", String(30), nullable=True)`
- Migration SQL (line 232): `ALTER TABLE posts ADD COLUMN content_format VARCHAR(30)`
- PATCH endpoint (line 176): lists `content_format` as a new parameter
- Cohort dimension enum (line 152): uses `content_format` in the allowed dimension list
- Suggested values section (line 219): labels the category as "Formats (content_format)"
- Acceptance criteria (line 457): uses `content_format`

No residual references to a bare `format` column remain. Fully addressed.

### M2. PATCH endpoint uses query parameters for all fields -- ACKNOWLEDGED (not in scope)

The revised plan continues to use query parameters for the PATCH endpoint, consistent with the existing codebase pattern. The initial review noted this was not a blocking issue for a single-user local tool and recommended documenting it as technical debt. The plan does not explicitly call this out as tech debt in a dedicated section, but the approach is consistent with the established API pattern and the scope of this feature. This is acceptable.

**Status:** Not a concern for this plan. Remains as general codebase tech debt for a future API refactor.

### M3. Rolling average None guard -- RESOLVED

The revised plan's `_compute_rolling_avg` implementation (line 521) now includes the `or 0.0` guard:

```python
avg = sum((p.engagement_rate or 0.0) for p in window_posts) / len(window_posts)
```

This matches the pattern used elsewhere in the codebase (e.g., `_serialize_post()`). Fully addressed.

---

## Previous Minor Concerns: Resolution Status

**m1. Monthly median missing `median_weighted_score` -- RESOLVED.** The `_compute_monthly_medians` implementation (lines 546-566) now computes both `median_engagement_rate` and `median_weighted_score`, and operates on full Post objects to access the `weighted_score` property. Spec and implementation are aligned.

**m2. Top 10% threshold with few posts -- UNCHANGED.** The plan still does not apply a minimum-post-count guard to the threshold calculation. Low risk given the plan already handles the "fewer than 5 posts" case for rolling averages. The implementer should consider omitting the threshold line when fewer than 5 posts exist.

**m3. `post_hour` validation -- UNCHANGED.** The PATCH endpoint extension (line 176) does not specify `ge=0, le=23` bounds on `post_hour`. The implementer should add these constraints.

**m4. `length_bucket` auto-calculation language -- RESOLVED.** The revised plan no longer mentions auto-calculation for `length_bucket`. Line 78 describes it as a user-supplied field, and the Assumptions section (line 55) confirms cohort metadata is "user-supplied classifications."

**m5. No test for migration script -- UNCHANGED.** Still no automated test for the migration script. Low risk since the script is idempotent and straightforward, but an integration test would be a good addition during implementation.

**m6. `seeded_client` fixture naming -- UNCHANGED.** The test signatures still use `seeded_client` without showing destructuring. The implementer should follow the existing `(TestClient, Session)` tuple pattern.

---

## New Concerns

### Minor

**m7. `content_format` column mapping is redundant**

Line 76 specifies `Column("content_format", String(30), nullable=True)` with an explicit column name argument. Since the Python attribute is also `content_format`, the explicit `"content_format"` string argument is unnecessary (SQLAlchemy defaults to using the attribute name). This is not a bug; it is just redundant. No action needed, but the implementer can simplify to `Column(String(30), nullable=True)`.

**m8. Metric relationship note could be clearer in the template spec**

The plan includes a thorough metric relationship note (lines 99) explaining the difference between `engagement_rate` and `weighted_score`. However, the analytics template section (lines 184-196) does not specify exact chart axis labels or tooltip text that would make this distinction clear to the user. The implementer should ensure chart legends use labels like "Engagement Rate (unweighted)" and "Weighted Score (comments 3x, shares 4x)" rather than bare metric names.

---

## Summary

The revised plan addresses all three Major concerns from the initial review. M1 (`content_format` rename) and M3 (None guard) are fully resolved in the plan text. M2 (PATCH query params) is correctly scoped out as existing tech debt. Two minor concerns from the initial review (m2, m3) remain as implementation-time items but are not blocking. Two new minor concerns (m7, m8) were identified, neither of which is blocking. The plan is ready for implementation.
