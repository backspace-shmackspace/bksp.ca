# Technical Implementation Plan: Engagement Quality Analytics

**Feature:** Engagement quality analytics page for the LinkedIn Analytics Dashboard
**Created:** 2026-02-28
**Author:** Architect

---

## Context Alignment

### CLAUDE.md Patterns Followed
- **Dark theme consistency:** Navy #0a0f1a background, #111827 cards, #f1f5f9 text, #3b82f6 accent. Inter + JetBrains Mono fonts via CDN.
- **Existing stack:** FastAPI + SQLAlchemy + SQLite + Jinja2 + Chart.js + Tailwind CDN. No new dependencies introduced.
- **Sensitivity protocol:** Dashboard is local/self-hosted. No employer-identifiable data is stored or displayed. Cohort labels (topic, format, hook style) are user-defined and do not reference employers.
- **No em-dashes:** All copy in templates and this plan avoids em-dashes.
- **Content pipeline integration:** This feature provides feedback on which content topics, formats, and hook styles drive the highest quality engagement, directly supporting the `/mine` and `/repurpose` pipeline.

### Prior Plans Consulted
- `plans/linkedin-analytics-dashboard.md` (APPROVED): Established the FastAPI/SQLite/Chart.js architecture, database schema, API patterns, template structure, and Docker deployment. This plan extends Phase 1 with a new analytics page, new model fields, new API endpoints, and new Chart.js visualizations.
- `plans/linkedin-analytics-dashboard.review.md` (PASS): Librarian review confirmed the architecture.
- `plans/linkedin-analytics-dashboard.redteam.md` (PASS): Red team review confirmed security posture.
- `plans/bksp-ca-astro-cloudflare-blog.md` (APPROVED): Reviewed for scope conflicts. The blog plan's "No analytics in v1" non-goal refers to Cloudflare Web Analytics on the blog site, not the LinkedIn analytics dashboard. No conflicts.

### Deviations from Established Patterns
- **New columns on Post model without Alembic:** The project does not use Alembic for migrations. The original plan uses `create_all()` on startup, which only creates missing tables (it does not add columns to existing tables). This plan includes a one-time SQL migration script that adds the new columns to the existing `posts` table. This is consistent with the project's "single-user home lab tool" philosophy where a full migration framework is unnecessary overhead.
- **Computed property (weighted_score) instead of stored column:** `weighted_score` is derived from existing columns using a fixed formula. Storing it would require recalculation on every metric update. A Python `@property` is simpler and consistent with the existing `display_title` property pattern. If query performance becomes an issue with hundreds of posts, a stored column can be added later.

---

## Goals

1. Track per-post engagement rate over time and visualize the trend
2. Compute a 5-post rolling average of engagement rate to smooth algorithm variance and show trend direction
3. Compute a quality-weighted engagement score: `((1 * reactions) + (3 * comments) + (4 * shares)) / impressions`
4. Enable cohort analysis by segmenting posts by topic, format, hook style, length, and time posted
5. Display five visualizations: engagement rate over time (line), rolling average trend, median engagement rate by month, top 10% post threshold, and baseline vs last 30 days comparison
6. Provide a UI for tagging posts with cohort metadata (topic, format, hook style)

## Non-Goals

- No predictive analytics or ML-based recommendations (future consideration)
- No integration with external analytics platforms (Google Analytics, etc.)
- No automated cohort classification (user manually tags posts)
- No A/B testing framework
- No export of analytics charts as images or PDFs
- No real-time updates (data refreshes on page load)

## Assumptions

1. The existing Post model and database schema are stable and deployed
2. There are at least 2 posts in the database (current state); the UI will degrade gracefully with fewer posts
3. Cohort metadata (topic, format, hook style) will be manually assigned by the user via the post detail page
4. The 5-post rolling average is calculated in Python, not SQL, since the dataset is small (tens of posts, not thousands)
5. LinkedIn export data does not include topic/content_format/hook_style metadata; these are user-supplied classifications
6. The `post_hour` field can be derived from `post_date` if time-of-day data becomes available in exports; for now it will be manually set

## Proposed Design

### Architecture Overview

This feature adds:
1. Five new nullable columns to the `Post` model (cohort metadata)
2. One new computed property on the `Post` model (`weighted_score`)
3. Two new API endpoints (`/api/analytics/engagement`, `/api/analytics/cohorts`)
4. One new page route (`/dashboard/analytics`)
5. One new template (`analytics.html`)
6. New Chart.js initialization function (`initAnalytics`)
7. Cohort tagging UI on the existing post detail page
8. One migration script to add columns to the existing database

### Data Model Changes

```python
# New columns on Post model (all nullable, user-supplied)
topic: str | None = Column(String(50), nullable=True)          # e.g. "risk-management", "devsecops", "htb-writeup"
content_format: str | None = Column("content_format", String(30), nullable=True)  # e.g. "story", "listicle", "hot-take", "tutorial", "case-study"
hook_style: str | None = Column(String(30), nullable=True)     # e.g. "question", "statistic", "contrarian", "personal", "news-hook"
length_bucket: str | None = Column(String(20), nullable=True)  # e.g. "short" (<500 chars), "medium" (500-1500), "long" (>1500)
post_hour: int | None = Column(Integer, nullable=True)         # 0-23, hour of day post was published

# Computed property (not stored)
@property
def weighted_score(self) -> float:
    """Quality-weighted engagement score.

    Formula: ((1 * reactions) + (3 * comments) + (4 * shares)) / impressions
    Comments weighted 3x (signal deeper engagement).
    Shares weighted 4x (signal advocacy/amplification).
    """
    if not self.impressions or self.impressions == 0:
        return 0.0
    return (
        (1 * (self.reactions or 0))
        + (3 * (self.comments or 0))
        + (4 * (self.shares or 0))
    ) / self.impressions
```

**Metric relationship note:** `engagement_rate` (existing, stored) and `weighted_score` (new, computed) measure different things. `engagement_rate` is `(reactions + comments + shares) / impressions`, treating all interaction types equally. `weighted_score` applies multipliers (1x reactions, 3x comments, 4x shares) to reflect signal quality: shares indicate advocacy, comments indicate depth, reactions indicate passive acknowledgment. The rolling average trend line tracks `engagement_rate` only (unweighted). The baseline vs last 30 days KPI cards and the monthly median chart show both metrics side by side. Chart legends and tooltip text must label these clearly so the user understands which metric each visualization tracks.

### API Design

#### `GET /api/analytics/engagement`

Returns all data needed for the five engagement visualizations.

**Query parameters:**
- `days` (int, default 365, min 30, max 1825): Lookback window

**Response shape:**
```json
{
  "posts": [
    {
      "id": 1,
      "post_date": "2025-11-01",
      "title": "Post title",
      "engagement_rate": 0.045,
      "weighted_score": 0.072,
      "rolling_avg_5": 0.038,
      "impressions": 3200,
      "reactions": 80,
      "comments": 15,
      "shares": 8
    }
  ],
  "monthly_medians": [
    {"month": "2025-11", "median_engagement_rate": 0.041, "median_weighted_score": 0.065}
  ],
  "top_10pct_threshold": 0.068,
  "baseline": {
    "avg_engagement_rate": 0.035,
    "avg_weighted_score": 0.052,
    "post_count": 15
  },
  "last_30d": {
    "avg_engagement_rate": 0.042,
    "avg_weighted_score": 0.061,
    "post_count": 4
  },
  "period_days": 365
}
```

The `rolling_avg_5` is computed server-side by sorting posts by date and averaging each post's engagement rate with its 4 predecessors. Posts with fewer than 5 predecessors use whatever is available (e.g., the first post's rolling average equals its own engagement rate).

#### `GET /api/analytics/cohorts`

Returns engagement metrics grouped by cohort dimension.

**Query parameters:**
- `dimension` (string, required, one of: `topic`, `content_format`, `hook_style`, `length_bucket`, `post_hour`): The cohort dimension to group by

**Response shape:**
```json
{
  "dimension": "topic",
  "cohorts": [
    {
      "value": "risk-management",
      "post_count": 5,
      "avg_engagement_rate": 0.045,
      "avg_weighted_score": 0.068,
      "median_engagement_rate": 0.042,
      "best_post_id": 3,
      "best_post_title": "Some post title"
    }
  ]
}
```

Only posts that have the requested dimension populated are included. Posts with null values for the dimension are excluded.

#### `PATCH /api/posts/{post_id}` (existing, extended)

Add support for new query parameters: `topic`, `content_format`, `hook_style`, `length_bucket`, `post_hour`.

All string cohort fields (`topic`, `content_format`, `hook_style`, `length_bucket`) are normalized on input before storage: lowercased, stripped of leading/trailing whitespace, and internal spaces replaced with hyphens. Empty strings are stored as null. This prevents cohort fragmentation from inconsistent tagging (e.g., `"Risk Management"` and `"risk-management"` both normalize to `"risk-management"`).

### Page Route

#### `GET /dashboard/analytics`

Server-rendered page with five visualization cards:

1. **Engagement Rate Over Time (line chart):** X-axis = post date, Y-axis = engagement rate (%). Each post is a data point. Line connects them chronologically.

2. **Rolling Average Trend (line chart, overlaid on #1):** Second dataset on the same chart showing the 5-post rolling average as a smoothed line. Uses a different color (success green #22c55e) to distinguish from the raw engagement rate line (accent blue #3b82f6).

3. **Median Engagement Rate by Month (bar chart):** One bar per calendar month. Shows the median (not mean) engagement rate for posts published in that month. More robust to outliers than average.

4. **Top 10% Post Threshold (horizontal line on chart #1):** A horizontal dashed line on the engagement rate chart showing the engagement rate that separates the top 10% of posts. If this line rises over time, the bar is rising.

5. **Baseline vs Last 30 Days Comparison (KPI cards):** Side-by-side cards showing: all-time average engagement rate vs last 30 days, all-time average weighted score vs last 30 days, with delta indicators (green up arrow or red down arrow).

Below the charts, a **Cohort Breakdown** section with a dimension selector (dropdown: Topic, Format, Hook Style, Length, Time Posted) and a table showing per-cohort stats.

### Sidebar Navigation Update

Add "Analytics" as a new nav item in `base.html`, positioned between "Dashboard" and "Audience". Icon: chart-bar-square (analytics feel).

### Post Detail Page Update

Add a "Content Tags" section below the existing "Lifetime Metrics" card on `post_detail.html`. This section contains:
- Topic: dropdown/text input
- Format: dropdown with preset options (stored as `content_format`)
- Hook Style: dropdown with preset options
- Length: dropdown with preset options (`short`, `medium`, `long`)
- Post Hour: number input (0-23)

Tags are saved via the existing `PATCH /api/posts/{id}` endpoint (extended with new params).

### Suggested Cohort Values

To keep the UI consistent and useful, the dropdowns will offer preset values (but allow free text):

**Topics:** `risk-management`, `devsecops`, `psirt`, `htb-writeup`, `ai-agents`, `career`, `leadership`, `security-culture`, `vulnerability-management`, `compliance`

**Formats (content_format):** `story`, `listicle`, `hot-take`, `tutorial`, `case-study`, `data-analysis`, `question`, `announcement`

**Hook Styles:** `question`, `statistic`, `contrarian`, `personal-story`, `news-hook`, `bold-claim`, `how-to`, `mistake-learned`

**Length Buckets:** `short` (<500 chars), `medium` (500-1500), `long` (>1500)

## Interfaces / Schema Changes

### Database Schema Additions

```sql
-- Migration: add cohort columns to posts table
ALTER TABLE posts ADD COLUMN topic VARCHAR(50);
ALTER TABLE posts ADD COLUMN content_format VARCHAR(30);
ALTER TABLE posts ADD COLUMN hook_style VARCHAR(30);
ALTER TABLE posts ADD COLUMN length_bucket VARCHAR(20);
ALTER TABLE posts ADD COLUMN post_hour INTEGER;
```

No new tables are created. No existing columns are modified. All new columns are nullable (no default required).

### API Endpoint Summary

| Method | Path | Description | New? |
|---|---|---|---|
| GET | `/api/analytics/engagement` | Engagement rate time series, rolling avg, monthly medians, thresholds | Yes |
| GET | `/api/analytics/cohorts?dimension={dim}` | Cohort breakdown by dimension | Yes |
| PATCH | `/api/posts/{id}` | Extended with topic, content_format, hook_style, length_bucket, post_hour params | Modified |
| GET | `/dashboard/analytics` | Analytics page (server-rendered) | Yes |

### Template Changes

| Template | Change |
|---|---|
| `base.html` | Add "Analytics" nav item to sidebar |
| `post_detail.html` | Add "Content Tags" section with cohort inputs |
| `analytics.html` | New template: 5 charts + cohort table |

### JavaScript Changes

| File | Change |
|---|---|
| `charts.js` | Add `initAnalytics(config)` function with line chart, bar chart, and threshold rendering |

## Data Migration

### Migration Script: `scripts/migrate_001_cohort_columns.py`

```python
"""Add cohort analysis columns to the posts table.

Run once after deploying this feature:
    python scripts/migrate_001_cohort_columns.py

Idempotent: safe to run multiple times (checks for column existence).
"""
import sqlite3
from app.config import settings

def migrate():
    conn = sqlite3.connect(str(settings.db_path))
    cursor = conn.cursor()

    # Get existing columns
    cursor.execute("PRAGMA table_info(posts)")
    existing = {row[1] for row in cursor.fetchall()}

    migrations = [
        ("topic", "VARCHAR(50)"),
        ("content_format", "VARCHAR(30)"),
        ("hook_style", "VARCHAR(30)"),
        ("length_bucket", "VARCHAR(20)"),
        ("post_hour", "INTEGER"),
    ]

    for col_name, col_type in migrations:
        if col_name not in existing:
            cursor.execute(f"ALTER TABLE posts ADD COLUMN {col_name} {col_type}")
            print(f"Added column: {col_name}")
        else:
            print(f"Column already exists: {col_name}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
```

### Alternative: Auto-migration on Startup

Since `Base.metadata.create_all()` does not add new columns to existing tables, and the project does not use Alembic, the migration script is the recommended approach. As a convenience, the script can be called from the lifespan startup if preferred, but running it manually is safer for a first deployment.

### Data Backfill

No automatic backfill is needed. Existing posts will have null values for all cohort columns. The user tags posts manually through the post detail UI. The analytics page handles null gracefully (excluded from cohort analysis, included in engagement rate charts).

## Rollout Plan

### Phase 1: Schema + API (backend)

1. Create migration script and run it against the existing database
2. Add new columns to the Post model in `models.py`
3. Add `weighted_score` property to Post model
4. Extend `PATCH /api/posts/{id}` with new parameters
5. Implement `GET /api/analytics/engagement` endpoint
6. Implement `GET /api/analytics/cohorts` endpoint
7. Update `_serialize_post()` to include new fields
8. Write tests for all new/modified endpoints

### Phase 2: Frontend (templates + charts)

9. Add "Analytics" nav item to `base.html`
10. Create `analytics.html` template
11. Add `initAnalytics()` function to `charts.js`
12. Add "Content Tags" section to `post_detail.html`
13. Add save handlers for cohort fields in post detail page
14. Manual testing of all visualizations

### Phase 3: Polish + Deploy

15. Docker rebuild and test
16. Tag existing posts with cohort metadata (manual, via UI)
17. Verify all charts render correctly with real data

## Risks

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Too few posts for meaningful rolling average | Charts look sparse/misleading | High (currently 2 posts) | Show a "Not enough data" message when fewer than 5 posts exist. The rolling average line uses however many predecessors are available. |
| Cohort tagging is tedious with many posts | User skips tagging, cohort analysis is empty | Medium | Provide presets in dropdowns (not free text only). Add a "bulk tag" feature in a future iteration. Start by tagging the few posts that exist. |
| Cohort input inconsistency | Fragmented cohort data from varied casing/spacing | Medium | All string cohort fields are normalized on input (lowercase, strip, spaces to hyphens). Empty strings stored as null. |
| Monthly median with 1 post per month | Median equals the single value, not statistically meaningful | Medium | Display post count per month alongside the bar. User understands significance. |
| Chart.js performance with many datasets | Slow rendering | Very Low | Even 100 posts is trivial for Chart.js. No mitigation needed. |
| Migration script fails on locked database | Migration cannot complete | Low | Script uses direct sqlite3 connection (not SQLAlchemy) and is idempotent. Retry after stopping the app if WAL lock is held. |

## Test Plan

### Test Command

```bash
# From linkedin-analytics directory (without Docker)
cd ~/bksp/linkedin-analytics && python -m pytest tests/ -v --tb=short

# With Docker
docker compose run --rm app pytest tests/ -v --tb=short
```

### New Test Cases

**`tests/test_models.py` (additions):**
- `test_weighted_score_calculation`: Verify weighted score formula with known values
- `test_weighted_score_zero_impressions`: Returns 0.0 when impressions is 0
- `test_cohort_fields_nullable`: All cohort columns accept null values
- `test_cohort_fields_persist`: Set and retrieve topic, content_format, hook_style, length_bucket, post_hour

**`tests/test_routes.py` (additions):**

```python
class TestAnalyticsEngagementApi:
    def test_engagement_empty_db(self, client):
        """Returns valid structure with empty data."""

    def test_engagement_with_data(self, seeded_client):
        """Returns posts, monthly_medians, threshold, baseline, last_30d."""

    def test_engagement_rolling_avg(self, seeded_client):
        """Rolling average is computed correctly for 5+ posts."""

    def test_engagement_rolling_avg_few_posts(self, seeded_client):
        """Rolling average handles fewer than 5 posts gracefully."""

    def test_engagement_weighted_score(self, seeded_client):
        """Weighted score matches manual calculation."""

    def test_engagement_top_10pct_threshold(self, seeded_client):
        """Top 10% threshold is correct for known data."""

class TestAnalyticsCohortApi:
    def test_cohorts_empty_db(self, client):
        """Returns valid structure with no cohorts."""

    def test_cohorts_by_topic(self, seeded_client):
        """Groups posts by topic correctly."""

    def test_cohorts_exclude_null(self, seeded_client):
        """Posts without the dimension set are excluded."""

    def test_invalid_dimension_rejected(self, client):
        """Unknown dimension returns 422."""

class TestPostUpdateCohortFields:
    def test_update_topic(self, seeded_client):
        """PATCH with topic updates the field."""

    def test_update_all_cohort_fields(self, seeded_client):
        """PATCH with all cohort fields updates them simultaneously."""

    def test_clear_cohort_field(self, seeded_client):
        """PATCH with empty string clears the field to null."""

class TestAnalyticsPage:
    def test_analytics_page_empty_db(self, client):
        """Page renders with empty state message."""

    def test_analytics_page_with_data(self, seeded_client):
        """Page renders with charts when data exists."""
```

### Existing Test Impact

All existing tests must continue to pass. The new columns are nullable with no defaults that affect existing behavior. The `_serialize_post()` changes add new keys to the response dict but do not remove or rename existing keys.

### Manual Testing Checklist

- [ ] Migration script runs successfully against existing database
- [ ] Migration script is idempotent (running twice does not error)
- [ ] Analytics page loads at `/dashboard/analytics` with empty database (shows empty state)
- [ ] Analytics page loads with seeded data (all 5 charts render)
- [ ] Engagement rate line chart shows one dot per post, chronologically
- [ ] Rolling average line overlays correctly on the engagement chart
- [ ] Top 10% threshold shows as a horizontal dashed line
- [ ] Monthly median bar chart shows one bar per month
- [ ] Baseline vs last 30 days KPI cards show correct values with delta arrows
- [ ] Cohort dimension selector changes the cohort table
- [ ] Post detail page shows "Content Tags" section
- [ ] Saving topic/content_format/hook_style/length_bucket/post_hour via post detail works
- [ ] Cohort table updates after tagging a post and reloading analytics
- [ ] Sidebar nav shows "Analytics" link with correct active state
- [ ] All existing pages (dashboard, audience, upload, post detail) still work
- [ ] Docker build succeeds and app starts correctly

## Acceptance Criteria

1. `GET /api/analytics/engagement` returns engagement rate, rolling average, monthly medians, top 10% threshold, and baseline vs last 30 days comparison for all posts
2. `GET /api/analytics/cohorts?dimension=topic` returns per-cohort average engagement rate, weighted score, and post count
3. The analytics page at `/dashboard/analytics` renders all 5 requested visualizations using Chart.js
4. Posts can be tagged with topic, content_format, hook_style, length_bucket, and post_hour via the post detail page
5. Weighted score is computed as `((1 * reactions) + (3 * comments) + (4 * shares)) / impressions`
6. Rolling average uses a 5-post window, handling edge cases (fewer than 5 posts)
7. The analytics page handles empty database gracefully (no errors, shows empty state)
8. All existing tests pass without modification
9. All new tests pass
10. The migration script is idempotent and runs without error on the existing database
11. No em-dashes appear anywhere in templates or copy

## Task Breakdown

### Files to Create

| File | Description |
|---|---|
| `linkedin-analytics/scripts/migrate_001_cohort_columns.py` | One-time migration: add 5 cohort columns to posts table. Idempotent. |
| `linkedin-analytics/app/templates/analytics.html` | Analytics page template: 5 chart canvases, cohort table, dimension selector, baseline vs last 30d KPI cards. Extends `base.html`. |

### Files to Modify

| File | Changes |
|---|---|
| `linkedin-analytics/app/models.py` | Add 5 columns (topic, content_format, hook_style, length_bucket, post_hour). Add `weighted_score` @property. |
| `linkedin-analytics/app/routes/api.py` | Add `GET /api/analytics/engagement`, `GET /api/analytics/cohorts`. Extend `PATCH /api/posts/{id}` with cohort params. Update `_serialize_post()` with new fields. Add `_normalize_cohort_value()` helper for input normalization. |
| `linkedin-analytics/app/routes/dashboard.py` | Add `GET /dashboard/analytics` page route. |
| `linkedin-analytics/app/templates/base.html` | Add "Analytics" nav item to sidebar (between Dashboard and Audience). |
| `linkedin-analytics/app/templates/post_detail.html` | Add "Content Tags" card with dropdown/input fields for topic, content_format, hook_style, length_bucket, post_hour. Add save handler JavaScript. |
| `linkedin-analytics/app/static/js/charts.js` | Add `initAnalytics(config)` function. Implements: engagement rate + rolling avg line chart with threshold line, monthly median bar chart. |
| `linkedin-analytics/tests/test_models.py` | Add tests for weighted_score property and cohort field persistence. |
| `linkedin-analytics/tests/test_routes.py` | Add TestAnalyticsEngagementApi, TestAnalyticsCohortApi, TestPostUpdateCohortFields, TestAnalyticsPage test classes. |
| `linkedin-analytics/tests/conftest.py` | Add `sample_posts_with_cohorts` fixture that creates posts with topic/content_format/hook_style populated. |

### Implementation Order

1. `scripts/migrate_001_cohort_columns.py` (migration script)
2. `app/models.py` (add columns + weighted_score property)
3. `app/routes/api.py` (extend PATCH, add analytics endpoints)
4. `tests/conftest.py` (add cohort fixtures)
5. `tests/test_models.py` (add weighted_score and cohort tests)
6. `tests/test_routes.py` (add analytics endpoint tests)
7. Run tests, verify all pass
8. `app/routes/dashboard.py` (add analytics page route)
9. `app/templates/base.html` (add nav item)
10. `app/templates/analytics.html` (new page template)
11. `app/static/js/charts.js` (add initAnalytics function)
12. `app/templates/post_detail.html` (add content tags section)
13. Full test suite run
14. Manual testing with real data
15. Docker rebuild and verify

### Detailed Implementation Notes

#### Rolling Average Calculation (in `api.py`)

```python
def _compute_rolling_avg(posts: list[Post], window: int = 5) -> list[float]:
    """Compute rolling average of engagement_rate over a sorted list of posts.

    For the first N posts where N < window, average over all available.
    """
    result = []
    for i, post in enumerate(posts):
        start = max(0, i - window + 1)
        window_posts = posts[start:i + 1]
        avg = sum((p.engagement_rate or 0.0) for p in window_posts) / len(window_posts)
        result.append(round(avg, 6))
    return result
```

#### Top 10% Threshold Calculation

```python
import math

def _compute_top_10pct_threshold(engagement_rates: list[float]) -> float:
    """Return the engagement rate at the 90th percentile."""
    if not engagement_rates:
        return 0.0
    sorted_rates = sorted(engagement_rates)
    idx = math.ceil(len(sorted_rates) * 0.9) - 1
    return sorted_rates[max(0, idx)]
```

#### Monthly Median Calculation

```python
import statistics
from collections import defaultdict

def _compute_monthly_medians(posts: list[Post]) -> list[dict]:
    """Group posts by YYYY-MM and compute median engagement rate and weighted score per month."""
    by_month: dict[str, list[Post]] = defaultdict(list)
    for p in posts:
        key = p.post_date.strftime("%Y-%m")
        by_month[key].append(p)

    return [
        {
            "month": month,
            "median_engagement_rate": round(
                statistics.median((p.engagement_rate or 0.0) for p in month_posts), 6
            ),
            "median_weighted_score": round(
                statistics.median(p.weighted_score for p in month_posts), 6
            ),
            "post_count": len(month_posts),
        }
        for month, month_posts in sorted(by_month.items())
    ]
```

#### Chart.js: Threshold Line

Chart.js supports annotation plugins, but to avoid adding a new CDN dependency, the threshold line can be rendered as a flat dataset:

```javascript
{
  label: "Top 10% Threshold",
  data: labels.map(() => threshold),  // same value for all x points
  borderColor: "#f59e0b",
  borderDash: [6, 4],
  borderWidth: 1,
  pointRadius: 0,
  fill: false,
}
```

## Status: APPROVED

---

<!-- Context Metadata
discovered_at: 2026-02-28T12:00:00Z
claude_md_exists: true
recent_plans_consulted: linkedin-analytics-dashboard.md, bksp-ca-astro-cloudflare-blog.md
archived_plans_consulted: linkedin-analytics-dashboard.feasibility.md, linkedin-analytics-dashboard.code-review.md
-->
