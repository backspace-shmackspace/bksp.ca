# LinkedIn Analytics Dashboard

A self-hosted dashboard for tracking LinkedIn content performance. Runs in Docker, stores data in SQLite, and ingests LinkedIn analytics exports via a web UI.

**Dashboard port:** `http://localhost:8050`

---

## Quick Start

```bash
cp .env.example .env
docker compose up -d
open http://localhost:8050
```

Then upload a LinkedIn analytics export at `/upload`.

---

## Getting a LinkedIn Export

1. Go to `linkedin.com/analytics/creator/content/`
2. Click **Export** (top right)
3. Select a date range (max 365 days)
4. Download the `.xlsx` file
5. Upload it at `http://localhost:8050/upload`

**Note:** The export format is provisional. If column names in your export differ from what the parser expects, check the warnings displayed after upload.

---

## Development (without Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set local data directory
export DATA_DIR=./data
export LOG_LEVEL=debug

# Seed sample data
python scripts/seed_sample.py

# Run the server
uvicorn app.main:app --reload --port 8050
```

### Run tests

```bash
python -m pytest tests/ -v --tb=short
```

### Run tests in Docker

```bash
docker compose run --rm app pytest tests/ -v --tb=short
```

---

## Architecture

```
linkedin-analytics/
  app/
    main.py          FastAPI app factory
    config.py        Settings (pydantic-settings, reads .env)
    models.py        SQLAlchemy models: Post, DailyMetric, FollowerSnapshot,
                     DemographicSnapshot, Upload
    database.py      Engine, SessionLocal, init_db()
    ingest.py        XLS/XLSX parser and DB loader
    routes/
      dashboard.py   Page routes: /, /dashboard, /dashboard/posts/{id}, /dashboard/audience
      api.py         JSON API: /api/metrics/*, /api/posts, /api/demographics, /api/followers, /health
      upload.py      GET/POST /upload
    templates/       Jinja2 templates (dark theme, Tailwind CDN, Chart.js)
    static/          CSS and JS
  data/
    linkedin.db      SQLite database (gitignored, backed up via bind mount)
    uploads/         Raw uploaded files (gitignored)
  scripts/
    seed_sample.py   Generate 90 days of sample data
  tests/             pytest test suite
```

---

## Data Persistence and Backup

Data is stored in `./data/linkedin.db` (relative to the project directory). The Docker Compose file uses a bind mount, not a named volume, so this file is always accessible on the host.

**Backup options:**

1. Download via the dashboard: `GET /api/export/db` downloads the SQLite file directly.
2. Include `./linkedin-analytics/data/` in your existing host backup solution.
3. Manual copy: `cp data/linkedin.db backups/linkedin-$(date +%Y%m%d).db`

**Restore:**

```bash
docker compose down
cp backups/linkedin-20251130.db data/linkedin.db
docker compose up -d
```

---

## API Reference

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/dashboard` | Main dashboard page |
| GET | `/dashboard/posts/{id}` | Post detail page |
| GET | `/dashboard/audience` | Audience demographics |
| GET | `/upload` | Upload form |
| POST | `/upload` | Handle file upload |
| GET | `/api/metrics/summary` | KPI summary JSON |
| GET | `/api/metrics/timeseries` | Daily time series JSON |
| GET | `/api/posts` | Paginated post list JSON |
| GET | `/api/posts/{id}` | Single post JSON |
| GET | `/api/demographics` | Demographic breakdown JSON |
| GET | `/api/followers/trend` | Follower growth JSON |
| GET | `/api/export/db` | Download SQLite database |

Full interactive API docs at `/docs`.

---

## Proxmox Deployment

1. Create an LXC container (Debian/Ubuntu) with Docker installed
2. Clone the repository
3. Copy `.env.example` to `.env`
4. Run `docker compose up -d`
5. Access at `http://<proxmox-host-ip>:8050`

Ensure port 8050 is forwarded through the Proxmox network bridge.

---

## Schema Note

The database schema is **provisional**. It is based on third-party documentation of the LinkedIn export format, not a verified real export. After uploading your first real export, check the warnings returned by the upload endpoint. If column names differ from what the parser expects, the schema and parser will need adjustment.

Fields that do not exist in the real export will be ignored. Fields present in the real export but not in the schema will need to be added to `app/models.py` and `app/ingest.py`.

---

## Limitations

- LinkedIn API requires a registered legal entity. This dashboard uses manual file export only.
- Exports are capped at 365 days by LinkedIn. Upload exports regularly to build historical data.
- Single-user only. Not designed for multi-tenant use.
- No posting to LinkedIn from the dashboard.
