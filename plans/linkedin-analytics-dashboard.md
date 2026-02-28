# Technical Implementation Plan: LinkedIn Analytics Dashboard

**Feature:** Self-hosted LinkedIn analytics dashboard for tracking content performance
**Created:** 2026-02-28
**Author:** Architect

---

## Context Alignment

### CLAUDE.md Patterns Followed
- **Docker/infrastructure:** CLAUDE.md notes Docker is not currently used in the project, but the user wants Docker for this new project. This plan introduces Docker as a standalone tool alongside the existing Astro blog.
- **Content pipeline awareness:** This dashboard supports the existing content pipeline (`/mine` -> `/publish` -> `/repurpose`) by providing feedback on LinkedIn content performance.
- **Sensitivity protocol:** The dashboard runs locally and stores only the user's own analytics data. No employer-identifiable information is involved. Any screenshots, README examples, or documentation must not expose post content that references Red Hat or employer-specific details.

### Prior Plans Consulted
- `plans/bksp-ca-astro-cloudflare-blog.md` (APPROVED): Established the Astro/Tailwind/Cloudflare stack for bksp.ca. This plan is a separate project (not part of bksp.ca) but follows the same design sensibilities (dark theme, Inter/JetBrains Mono fonts) for visual consistency.

### Deviations with Justification
- **Separate directory within bksp.ca repo:** This dashboard lives alongside the Astro site but is a standalone Python + Docker project. Rationale: different runtime (Python backend), different deployment target (local Docker / Proxmox), and different data flow (file ingestion, not static site generation). Shares the `backspace-shmackspace/bksp.ca` upstream repo for simplicity.
- **Python stack (not Astro):** Astro is a static site generator. This project needs a backend for data storage, scheduled ingestion, and a dynamic dashboard. Python with Flask/FastAPI and SQLite is the simplest self-contained stack for a home lab tool.

---

## Research Summary: LinkedIn API vs File-Based Approach

### LinkedIn API: Current State (2025-2026)

**Member Post Analytics API** (launched July 2025): LinkedIn now offers a `memberCreatorPostAnalytics` endpoint that returns per-post and aggregated metrics including impressions, members reached, reshares, reactions, and comments. This is accessed via the Community Management API.

**The blocker for individual developers:** The Community Management API is **only available to registered legal organizations** for commercial use cases. LinkedIn explicitly requires:
- A registered legal entity (LLC, corporation, 501(c), etc.)
- A business email address (personal email rejected)
- Organization legal name, registered address, website, and privacy policy
- LinkedIn Page verification by a super admin
- Screen recording of your application for Standard tier approval

An individual developer building a personal analytics dashboard does not qualify. This is confirmed by LinkedIn's official documentation: "At this time, our Community Management APIs are only available to registered legal organizations for commercial use cases only."

**LinkedIn Premium:** Premium membership gives enhanced in-app analytics (more detailed engagement demographics, longer history) but does **not** grant API access. API access is controlled by the Developer Portal, not by subscription tier.

### LinkedIn Manual Export: What You Get (PROVISIONAL)

**WARNING: The export format described below is based on third-party documentation, not a verified real export. Phase 0 (below) requires downloading and inspecting an actual export before any code is written. The schema, ingestion pipeline, and test fixtures must be finalized after Phase 0.**

LinkedIn provides manual CSV/XLS exports for personal profiles with analytics enabled. The export is believed to contain **5 sheets**:

| Sheet | Data |
|---|---|
| **DISCOVERY** | Impressions over time |
| **ENGAGEMENT** | Reactions, comments, shares, clicks per post |
| **TOP POSTS** | Best-performing posts with metrics |
| **FOLLOWERS** | Follower count over time, net new followers |
| **DEMOGRAPHICS** | Job titles, industries, seniority, locations of audience |

**Export path:** `linkedin.com/analytics/creator/content/` -> Export button (top right) -> XLS file

**Limitations:**
- Date range capped at 365 days maximum
- Profile views are NOT exportable
- No programmatic/automated export (manual browser action required)
- File format may be `.xls` (legacy BIFF) or `.xlsx` (Office Open XML); must be verified in Phase 0

### Recommendation: File-Based Approach (Phase 1) with API Upgrade Path (Phase 2)

**Primary approach: Manual CSV/XLS ingestion.** This is the only viable path for an individual developer without a registered legal entity. It works today, provides rich data (5 sheets of metrics), and requires zero API approval.

**Why not the API:**
1. LinkedIn's Community Management API requires a legal entity. An individual cannot get approved.
2. Even if approved, the Development tier has a 12-month window and API call restrictions.
3. The approval process takes weeks and frequently results in rejection with vague feedback.
4. Token refresh adds operational complexity for a home lab tool.

**Future upgrade path:** If Ian registers an LLC or similar entity for consulting/content work, the API path becomes viable. The dashboard schema is designed to be data-source agnostic, so switching from file ingestion to API ingestion would only require adding a new ingestion module, not redesigning the dashboard.

**Alternative considered: Third-party tools (Metricool, Buffer, etc.).** These approved partners already have API access and offer LinkedIn analytics. However, they are SaaS products (not self-hosted), most require paid subscriptions for useful features, and they don't give you raw data ownership. The whole point of this project is local data ownership and customization.

---

## Goals

1. Build a self-hosted LinkedIn analytics dashboard that runs in Docker (locally or on Proxmox)
2. Ingest LinkedIn analytics data from manual XLS/CSV exports
3. Track post-level metrics: impressions, reactions, comments, shares, clicks, members reached
4. Track account-level trends: follower growth, engagement rate over time, audience demographics
5. Provide a clean, dark-themed web dashboard for visualizing performance
6. Store historical data in SQLite for trend analysis beyond LinkedIn's 365-day export window
7. Design for eventual API integration if organizational requirements are met in the future

## Non-Goals

- No LinkedIn API integration in v1 (blocked by legal entity requirement)
- No automated scraping of LinkedIn (violates ToS, risk of account ban)
- No multi-user support (single user, single LinkedIn account)
- No posting to LinkedIn from the dashboard (use the `/repurpose` skill for that)
- No real-time data (manual export cadence, likely weekly)
- No mobile-native app (responsive web dashboard is sufficient)
- No integration with bksp.ca blog analytics (separate concern, add later if desired)

## Assumptions

1. Ian has Docker and Docker Compose installed (or will install on the target machine)
2. Ian has LinkedIn Premium and access to creator analytics exports
3. Exports will be done manually (weekly or bi-weekly cadence)
4. The dashboard will initially run on Ian's Mac, with a path to Proxmox deployment
5. Python 3.12+ is available for local development
6. The project will live in its own repository under the `backspace-shmackspace/bksp.ca` repo (alongside the Astro site)

## Proposed Design

### Architecture

```
linkedin-analytics/
  docker-compose.yml          # Single-command startup
  Dockerfile                  # Python app container
  app/
    main.py                   # FastAPI application entry point
    config.py                 # Configuration (paths, settings)
    models.py                 # SQLAlchemy models (SQLite)
    ingest.py                 # XLS/CSV parser and DB loader
    routes/
      dashboard.py            # Dashboard page routes
      api.py                  # JSON API for chart data
      upload.py               # File upload endpoint
    templates/
      base.html               # Jinja2 base template (dark theme)
      dashboard.html           # Main dashboard view
      post_detail.html         # Single post drill-down
      upload.html              # Upload form
    static/
      css/
        style.css             # Tailwind-compiled CSS (dark theme)
      js/
        charts.js             # Chart.js initialization
  data/
    uploads/                  # Raw uploaded XLS/CSV files (gitignored)
    linkedin.db               # SQLite database (gitignored)
  scripts/
    seed_sample.py            # Generate sample data for testing
  tests/
    test_ingest.py            # Ingestion parser tests
    test_models.py            # Database model tests
    test_routes.py            # API endpoint tests
    conftest.py               # Pytest fixtures
  requirements.txt            # Python dependencies
  .env.example                # Environment variable template
  .gitignore
  README.md
```

### Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Backend | FastAPI (Python 3.12) | Lightweight, async-capable, auto-generates API docs. Ian has Python experience from AI agent work. |
| Database | SQLite | Zero-config, single-file, perfect for single-user home lab. No separate DB container needed. |
| ORM | SQLAlchemy 2.0 | Type-safe, well-documented, works seamlessly with SQLite and FastAPI. |
| Templates | Jinja2 | Built into FastAPI/Starlette, server-rendered (no SPA complexity). |
| Charts | Chart.js 4.x | Lightweight, well-documented, renders client-side. No build step needed. |
| Styling | Tailwind CSS (CDN) | Consistent with bksp.ca aesthetic. CDN avoids build tooling for a backend project. |
| File parsing | openpyxl + xlrd + pandas | openpyxl reads `.xlsx`, xlrd reads legacy `.xls`. Actual format to be confirmed in Phase 0. pandas provides data transformation. |
| Container | Docker + Docker Compose | Single `docker compose up` to run everything. |
| Fonts | Inter + JetBrains Mono (CDN) | Visual consistency with bksp.ca. |

### Data Flow

```
LinkedIn Web UI
    |
    | (manual export, XLS file)
    v
Dashboard Upload Page (/upload)
    |
    | (openpyxl parses XLS)
    v
Ingestion Pipeline (ingest.py)
    |
    | (deduplicate, normalize, store)
    v
SQLite Database (linkedin.db)
    |
    | (SQLAlchemy queries)
    v
Dashboard Routes (/dashboard)
    |
    | (Jinja2 templates + Chart.js)
    v
Browser (dark-themed dashboard)
```

### Dashboard Views

**Main Dashboard (`/dashboard`)**
- KPI cards: total impressions (30d), engagement rate (30d), follower count, total posts tracked
- Line chart: impressions over time (daily, selectable range)
- Line chart: engagement rate over time
- Bar chart: reactions/comments/shares breakdown by post
- Table: recent posts with sortable metrics

**Post Detail (`/dashboard/posts/{id}`)**
- All metrics for a single post
- Daily impression trend (if daily data available)
- Engagement breakdown (reactions, comments, shares, clicks)

**Audience (`/dashboard/audience`)**
- Demographics charts: top industries, job titles, seniority levels, locations
- Follower growth trend line

**Upload (`/upload`)**
- Drag-and-drop or file picker for XLS/CSV files
- Upload history with timestamps
- Validation feedback (file format, duplicate detection)

### Post Deduplication Strategy

LinkedIn exports may not include a stable post identifier (URN). The deduplication strategy is:

1. **File-level dedup:** SHA256 hash of the uploaded file prevents re-importing the exact same file.
2. **Record-level dedup (overlapping exports):** Posts are matched using a composite key of `post_date` + `title` (first 100 characters of post text). When a match is found, metrics are updated using UPSERT semantics: the higher value wins for cumulative metrics (impressions, reactions, comments, shares, clicks), and `engagement_rate` is recalculated on every upsert.
3. **`linkedin_post_id`:** Used as the primary dedup key if present in the export. Falls back to the composite key strategy if not available.
4. **Daily metrics:** Deduplicated on the existing `(post_id, metric_date)` unique constraint, with UPSERT semantics.
5. **Follower/demographic snapshots:** Deduplicated on their existing unique constraints (`snapshot_date` for followers; `snapshot_date + category + value` for demographics), with UPSERT semantics.

This strategy will be validated against real export data in Phase 0 and adjusted if the actual format provides a better dedup key.

### SQLite Backup Strategy

The SQLite database is the sole store of historical data beyond LinkedIn's 365-day export window. Backup approach:

1. **Docker volume bind mount:** Use a bind mount (not a named volume) in `docker-compose.yml` so the `data/` directory maps to a known host path that can be included in existing host-level backups.
2. **Manual export endpoint:** `GET /api/export/db` returns a downloadable copy of the SQLite database file. This is a Phase 1 requirement (not deferred to Phase 2).
3. **Documentation:** The README includes instructions for backing up the `data/` directory and restoring from a backup.

## Interfaces / Schema Changes

### Database Schema (SQLite via SQLAlchemy) (PROVISIONAL)

**NOTE:** This schema is provisional. It is based on third-party documentation about the LinkedIn export format. Phase 0 requires downloading a real export and verifying the actual sheet names, column headers, and data types. The schema will be finalized after Phase 0. Fields that do not exist in the real export will be removed; fields present in the real export but missing here will be added.

```python
# models.py

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    linkedin_post_id = Column(String, unique=True, nullable=True)  # If extractable from export
    title = Column(String, nullable=True)                          # First ~100 chars of post text
    post_date = Column(Date, nullable=False)
    post_type = Column(String, nullable=True)                      # text, image, video, article, etc.
    impressions = Column(Integer, default=0)
    members_reached = Column(Integer, default=0)
    reactions = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)                   # Calculated: (reactions+comments+shares)/impressions
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    daily_metrics = relationship("DailyMetric", back_populates="post")


class DailyMetric(Base):
    __tablename__ = "daily_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)  # Null for account-level metrics
    metric_date = Column(Date, nullable=False)
    impressions = Column(Integer, default=0)
    members_reached = Column(Integer, default=0)
    reactions = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())

    post = relationship("Post", back_populates="daily_metrics")

    __table_args__ = (
        UniqueConstraint("post_id", "metric_date", name="uq_post_date"),
    )


class FollowerSnapshot(Base):
    __tablename__ = "follower_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, nullable=False, unique=True)
    total_followers = Column(Integer, nullable=False)
    new_followers = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())


class DemographicSnapshot(Base):
    __tablename__ = "demographic_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, nullable=False)
    category = Column(String, nullable=False)      # "industry", "job_title", "seniority", "location"
    value = Column(String, nullable=False)          # e.g., "Information Technology", "Director", etc.
    percentage = Column(Float, nullable=False)      # Percentage of audience
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        UniqueConstraint("snapshot_date", "category", "value", name="uq_demo_snapshot"),
    )


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String, nullable=False)
    file_hash = Column(String, nullable=False, unique=True)  # SHA256 for dedup
    upload_date = Column(DateTime, default=func.now())
    records_imported = Column(Integer, default=0)
    status = Column(String, default="completed")             # completed, failed, duplicate
```

### API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | Redirect to `/dashboard` |
| GET | `/dashboard` | Main dashboard page (server-rendered) |
| GET | `/dashboard/posts/{id}` | Post detail page |
| GET | `/dashboard/audience` | Audience demographics page |
| GET | `/upload` | Upload form page |
| POST | `/upload` | Handle file upload and ingestion |
| GET | `/api/metrics/summary` | JSON: KPI summary (30d impressions, engagement rate, follower count) |
| GET | `/api/metrics/timeseries?metric={metric}&days={n}` | JSON: time series data for charts |
| GET | `/api/posts?sort={field}&order={asc|desc}&limit={n}` | JSON: post list with metrics |
| GET | `/api/posts/{id}` | JSON: single post metrics |
| GET | `/api/demographics?category={category}` | JSON: demographic breakdown |
| GET | `/api/followers/trend?days={n}` | JSON: follower growth trend |
| GET | `/api/export/db` | Download: SQLite database file for backup |
| GET | `/health` | JSON: health check for Docker |

## Data Migration

No data migration required. This is a greenfield project. The database is created on first run via SQLAlchemy's `create_all()`.

Historical data can be bootstrapped by uploading past LinkedIn exports (up to 365 days back from the date of each export).

## Rollout Plan

### Phase 0: Export Format Verification (REQUIRED before any code)

1. Download a real LinkedIn analytics export from `linkedin.com/analytics/creator/content/`
2. Document the actual file format (`.xls` vs `.xlsx`)
3. Document exact sheet names and column headers for each sheet
4. Document data types, date formats, and any quirks (empty rows, merged cells, etc.)
5. Determine whether a stable post identifier (URN) is included in the export
6. Determine whether `members_reached` is present in the export
7. Finalize the database schema based on real data (update this plan)
8. Choose the correct parsing library: `openpyxl` for `.xlsx`, `xlrd` for `.xls`, or both with auto-detection
9. Create a redacted/synthetic test fixture that mirrors the real format exactly

**Gate:** Phase 1 cannot begin until Phase 0 is complete and this plan is updated with verified format details.

### Phase 1: Core Dashboard (this implementation)

1. Set up project structure and Docker configuration
2. Implement SQLAlchemy models and database initialization (finalized schema from Phase 0)
3. Build XLS/CSV ingestion pipeline with validation and record-level deduplication (UPSERT strategy)
4. Create FastAPI routes for dashboard pages and JSON API (including `/api/export/db`)
5. Build Jinja2 templates with Chart.js visualizations
6. Style with Tailwind CSS (dark theme matching bksp.ca)
7. Write tests for ingestion, models, and routes
8. Docker Compose configuration for one-command startup
9. Test with real LinkedIn export data

### Phase 2: Enhancements (future)

- Add data export (CSV/JSON from the dashboard)
- Add comparison views (this month vs last month)
- Add content tagging (map LinkedIn posts to bksp.ca content lanes)
- Add goal tracking (set target impressions/engagement, track progress)
- Scheduled reminders to export data (via email or webhook)

### Phase 3: API Integration (future, requires legal entity)

- Add LinkedIn OAuth flow
- Implement `memberCreatorPostAnalytics` API ingestion
- Add automated scheduled data pulls (replace manual export)
- The existing schema and dashboard work without changes; only the ingestion layer is swapped

## Risks

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| LinkedIn changes export format | Ingestion breaks | Medium | Version the parser; add format detection and validation with clear error messages. Keep sample exports in test fixtures. Phase 0 establishes the baseline format. |
| LinkedIn removes manual export | No new data ingestion | Low | Export feature has existed for years and is widely used. If removed, manual data entry or API path becomes necessary. |
| XLS parsing edge cases | Missing or corrupt data | Medium | Defensive parsing with try/except per row. Log warnings for unparseable rows. Validate imports before committing to DB. |
| SQLite concurrency limits | N/A for single user | Very Low | Single-user tool. SQLite handles this fine. If multi-user needed later, swap to PostgreSQL (SQLAlchemy makes this a config change). |
| Docker networking on Proxmox | Dashboard unreachable from LAN | Low | Use `host` network mode or explicit port mapping. Document Proxmox-specific network config. |
| Scope creep into API integration | Delays v1 delivery | Medium | API integration is explicitly Phase 3. v1 ships with file-based ingestion only. |
| Docker volume loss | All historical data lost permanently | Medium | Bind mount to host path (not named volume) enables host-level backups. `/api/export/db` endpoint provides manual backup. |
| Screenshots exposing employer content | Sensitivity protocol violation | Low | Any screenshots, README examples, or demo data must not reference Red Hat or employer-specific details. |

## Test Plan

### Test Command

```bash
# From project root
docker compose run --rm app pytest tests/ -v --tb=short

# Or without Docker (local development)
cd linkedin-analytics && python -m pytest tests/ -v --tb=short
```

### Test Coverage

**Ingestion Tests (`tests/test_ingest.py`)**
- Parse a sample LinkedIn XLS export with all 5 sheets
- Handle missing sheets gracefully (warn, not crash)
- Deduplicate: uploading the same file twice does not create duplicate records
- Handle malformed data (empty rows, missing columns, non-numeric values)
- Correctly calculate engagement rate from raw metrics

**Model Tests (`tests/test_models.py`)**
- Create and query Posts, DailyMetrics, FollowerSnapshots, DemographicSnapshots
- Unique constraints prevent duplicate entries
- Cascade deletes work correctly
- Engagement rate calculation is accurate

**Route Tests (`tests/test_routes.py`)**
- `GET /dashboard` returns 200 with empty database
- `GET /dashboard` returns 200 with populated database
- `POST /upload` with valid XLS returns 200 and imports data
- `POST /upload` with invalid file returns 400
- `POST /upload` with duplicate file returns 409
- `GET /api/metrics/summary` returns correct JSON structure
- `GET /api/metrics/timeseries` returns correct time series data
- `GET /api/posts` returns paginated, sorted results
- `GET /health` returns 200

**Sample Data (`scripts/seed_sample.py`)**
- Generates 90 days of realistic sample data for development and testing
- Creates 20 sample posts with varied metrics
- Generates daily metric entries and follower snapshots

### Manual Testing Checklist

- [ ] `docker compose up` starts the application without errors
- [ ] Dashboard loads at `http://localhost:8050`
- [ ] Upload a real LinkedIn XLS export via `/upload`
- [ ] Dashboard updates with imported data
- [ ] Charts render correctly (impressions trend, engagement breakdown)
- [ ] Post detail page shows per-post metrics
- [ ] Audience page shows demographic charts
- [ ] Uploading the same file again shows a duplicate warning
- [ ] Application survives container restart (data persists via bind mount)
- [ ] Health endpoint responds at `/health`
- [ ] `/api/export/db` downloads a valid SQLite database file

## Acceptance Criteria

1. `docker compose up` starts the dashboard with zero manual configuration beyond `.env`
2. Dashboard is accessible at `http://localhost:8050` with the dark theme
3. A LinkedIn XLS export can be uploaded via the web UI and data appears on the dashboard
4. Post-level metrics (impressions, reactions, comments, shares, clicks) are displayed per post
5. Time series charts show trends over selectable date ranges
6. Duplicate file uploads are detected and rejected
7. Data persists across container restarts (bind mount for SQLite, accessible for host-level backups)
8. All tests pass (`pytest tests/ -v` exits 0)
9. The application runs on both macOS (local Docker) and Linux (Proxmox Docker)
10. No LinkedIn credentials or API keys are required for v1

## Task Breakdown

### Files to Create

```
linkedin-analytics/
  docker-compose.yml                    # Docker Compose with app service, volume for data/
  Dockerfile                            # Python 3.12-slim, pip install, copy app
  requirements.txt                      # fastapi, uvicorn, sqlalchemy, openpyxl, xlrd, pandas,
                                        #   python-multipart, jinja2, pytest, httpx, aiofiles
  .env.example                          # APP_PORT=8050, DATA_DIR=/app/data, LOG_LEVEL=info
  .gitignore                            # data/, __pycache__, .env, *.pyc, .pytest_cache
  app/
    __init__.py
    main.py                             # FastAPI app factory, mount static/templates, include routers
    config.py                           # Settings from env vars (pydantic-settings)
    models.py                           # SQLAlchemy models: Post, DailyMetric, FollowerSnapshot,
                                        #   DemographicSnapshot, Upload
    database.py                         # Engine, SessionLocal, Base, create_all()
    ingest.py                           # parse_linkedin_export(file_path) -> structured data
                                        #   load_to_db(session, parsed_data) -> import stats
                                        #   compute_file_hash(file_path) -> sha256
    routes/
      __init__.py
      dashboard.py                      # GET /, GET /dashboard, GET /dashboard/posts/{id},
                                        #   GET /dashboard/audience
      api.py                            # GET /api/metrics/summary, /api/metrics/timeseries,
                                        #   /api/posts, /api/posts/{id}, /api/demographics,
                                        #   /api/followers/trend, /health
      upload.py                         # GET /upload (form), POST /upload (handle file)
    templates/
      base.html                         # HTML shell: dark theme, Inter/JetBrains Mono CDN,
                                        #   Tailwind CDN, Chart.js CDN, nav sidebar
      dashboard.html                    # KPI cards, impression chart, engagement chart,
                                        #   post table
      post_detail.html                  # Single post metrics, daily trend chart
      audience.html                     # Demographics charts (industry, title, seniority, location)
      upload.html                       # Drag-and-drop upload form, upload history table
      _partials/
        kpi_card.html                   # Reusable KPI card partial
        post_table.html                 # Reusable post metrics table partial
    static/
      css/
        style.css                       # Custom overrides beyond Tailwind CDN
      js/
        charts.js                       # Chart.js initialization and update functions
        upload.js                       # Drag-and-drop upload handling
  data/                                 # Created at runtime, gitignored
    .gitkeep                            # Ensure directory exists in repo
  scripts/
    seed_sample.py                      # Generate sample data for dev/testing
  tests/
    __init__.py
    conftest.py                         # Pytest fixtures: test DB, test client, sample XLS
    test_ingest.py                      # Ingestion pipeline tests
    test_models.py                      # Database model tests
    test_routes.py                      # API and page route tests
    fixtures/
      sample_export.xlsx                # Sample LinkedIn export for testing (synthetic data)
```

### Files to Modify

None. This is a greenfield project in a new repository (`backspace-shmackspace/bksp.ca` on GitHub, under the `linkedin-analytics/` directory).

### Implementation Order

**Phase 0 (must complete first):**
0. Download real LinkedIn export, document format, finalize schema and library choice (see Phase 0 in Rollout Plan)

**Phase 1:**
1. `requirements.txt` - pin dependencies (include both `openpyxl` and `xlrd`; remove whichever is unnecessary after Phase 0)
2. `app/config.py` - settings from environment
3. `app/models.py` + `app/database.py` - schema and DB setup (finalized from Phase 0)
4. `app/ingest.py` - XLS/XLSX parser with format auto-detection and record-level UPSERT dedup
5. `tests/conftest.py` + `tests/fixtures/sample_export.xlsx` - test infrastructure
6. `tests/test_models.py` - model tests
7. `tests/test_ingest.py` - ingestion tests
8. `app/routes/api.py` - JSON API endpoints
9. `app/routes/upload.py` - file upload handling
10. `app/routes/dashboard.py` - dashboard page routes
11. `tests/test_routes.py` - route tests
12. `app/templates/base.html` - base template with dark theme
13. `app/templates/dashboard.html` - main dashboard
14. `app/templates/post_detail.html` - post detail view
15. `app/templates/audience.html` - audience demographics
16. `app/templates/upload.html` - upload form
17. `app/static/js/charts.js` - Chart.js setup
18. `app/static/js/upload.js` - drag-and-drop upload
19. `app/static/css/style.css` - custom styles
20. `app/main.py` - FastAPI app factory, wire everything together
21. `scripts/seed_sample.py` - sample data generator
22. `Dockerfile` - container build
23. `docker-compose.yml` - compose configuration
24. `.env.example` + `.gitignore`
25. Full test suite run and manual verification
26. (Optional) Push to GitHub as new repo

### Docker Configuration

**Dockerfile:**
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY scripts/ ./scripts/

EXPOSE 8050

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8050"]
```

**docker-compose.yml:**
```yaml
services:
  app:
    build: .
    ports:
      - "${APP_PORT:-8050}:8050"
    volumes:
      - ./data:/app/data
    env_file:
      - .env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8050/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
```

**Note:** Uses a bind mount (`./data:/app/data`) instead of a named Docker volume so the SQLite database is at a known host path and can be included in host-level backups.

### Proxmox Deployment Notes

For deployment on Proxmox with Docker:

1. Create an LXC container (Debian/Ubuntu) or use an existing Docker-capable VM
2. Install Docker and Docker Compose in the container/VM
3. Clone the repository
4. Copy `.env.example` to `.env` and adjust `APP_PORT` if needed
5. Run `docker compose up -d`
6. Access at `http://<proxmox-host-ip>:8050`
7. For LAN access, ensure the Proxmox network bridge forwards the port

No special Proxmox configuration is needed beyond standard Docker networking.

## Status: APPROVED

---

### Research Sources

- [Member Post Statistics API Documentation (Microsoft Learn)](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/members/post-statistics?view=li-lms-2025-11)
- [Community Management App Review Requirements (Microsoft Learn)](https://learn.microsoft.com/en-us/linkedin/marketing/community-management-app-review?view=li-lms-2026-02)
- [Getting Access to LinkedIn APIs (Microsoft Learn)](https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access)
- [LinkedIn API Guide: How It Works in 2025 (OutXAI)](https://www.outx.ai/blog/linkedin-api-guide)
- [Export LinkedIn Analytics Guide (TryOrdinal)](https://www.tryordinal.com/blog/how-to-export-analytics-from-linkedin-to-excel-or-a-csv)
- [Export LinkedIn Analytics to Excel: 3 Methods (OutXAI)](https://www.outx.ai/blog/export-linkedin-analytics-excel)
- [LinkedIn Makes It Easier for Creators to Track Performance (Digiday)](https://digiday.com/media/linkedin-makes-it-easier-for-creators-to-track-performance-across-platforms/)
- [LinkedIn Analytics: A Guide to Tracking Metrics in 2026 (100PoundSocial)](https://100poundsocial.com/blog/linkedin/linkedin-analytics-guide/)
- [LinkedIn Creator Mode: Complete 2026 Guide (LinkedHelper)](https://www.linkedhelper.com/blog/linkedin-creator-mode/)
- [Increasing Access to LinkedIn APIs (Microsoft Learn)](https://learn.microsoft.com/en-us/linkedin/marketing/increasing-access?view=li-lms-2025-11)

<!-- Context Metadata
discovered_at: 2026-02-28T00:00:00Z
claude_md_exists: true
recent_plans_consulted: bksp-ca-astro-cloudflare-blog.md
archived_plans_consulted: none
-->
