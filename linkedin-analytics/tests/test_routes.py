"""Tests for API and dashboard page routes."""

import io
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_session
from app.models import Base, DailyMetric, DemographicSnapshot, FollowerSnapshot, Post, Upload


# ---------------------------------------------------------------------------
# Fixtures: shared-connection engine + seeded client
#
# Route tests require that data written in the test is visible to the routes.
# SQLite :memory: databases are per-connection. We solve this by binding all
# sessions (test and route override) to a single shared connection.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def _shared_engine():
    """Create an in-memory SQLite engine with a single shared connection."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def seeded_client(_shared_engine, tmp_path):
    """Return (TestClient, Session) where both use the same shared connection.

    The Session can be used to seed data before making requests. Data committed
    on the session will be visible to the route handlers since they share the
    same underlying connection.
    """
    from app.main import app
    from app import database as app_db
    from app import config as app_config

    shared_conn = _shared_engine.connect()
    SharedSession = sessionmaker(autocommit=False, autoflush=False, bind=shared_conn)

    def override_get_session():
        s = SharedSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = override_get_session

    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Override data_dir so uploads land in tmp_path.
    # We mutate the pydantic field value on the shared settings singleton
    # in place so that all modules that imported the same object (e.g.
    # app.database) see the updated value. uploads_dir and db_path are
    # @property methods that derive from data_dir, so they automatically
    # reflect the override — no separate field mutation is needed.
    original_data_dir = app_config.settings.__dict__["data_dir"]
    app_config.settings.__dict__["data_dir"] = tmp_path

    original_engine = app_db.engine
    original_session_local = app_db.SessionLocal
    app_db.engine = _shared_engine
    app_db.SessionLocal = SharedSession

    seed_session = SharedSession()

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c, seed_session

    seed_session.close()
    shared_conn.close()
    app.dependency_overrides.clear()
    app_db.engine = original_engine
    app_db.SessionLocal = original_session_local
    app_config.settings.__dict__["data_dir"] = original_data_dir


def _seed_db(db: Session) -> None:
    """Insert minimal test data into the database and commit.

    Uses dates relative to today so that the data falls within the
    API's default lookback windows (30d, 60d, 90d).
    """
    today = date.today()
    base = today - timedelta(days=29)  # 30 days back, inclusive of today
    for i in range(5):
        post = Post(
            post_date=base + timedelta(days=i * 5),
            title=f"Post number {i + 1}",
            post_type="text",
            impressions=1000 + i * 100,
            members_reached=800 + i * 80,
            reactions=50 + i * 5,
            comments=10 + i * 2,
            shares=5 + i,
            clicks=20 + i * 3,
        )
        post.recalculate_engagement_rate()
        db.add(post)

    for i in range(30):
        db.add(
            DailyMetric(
                post_id=None,
                metric_date=base + timedelta(days=i),
                impressions=200 + i * 10,
                members_reached=140 + i * 7,
            )
        )

    followers = 450
    for i in range(30):
        new = i % 5 + 1
        followers += new
        db.add(
            FollowerSnapshot(
                snapshot_date=base + timedelta(days=i),
                total_followers=followers,
                new_followers=new,
            )
        )

    snap_date = base + timedelta(days=29)  # = today
    for cat, val, pct in [
        ("industry", "IT", 32.5),
        ("industry", "Finance", 18.0),
        ("job_title", "Director", 22.0),
        ("seniority", "Senior", 40.0),
        ("location", "United States", 55.0),
    ]:
        db.add(
            DemographicSnapshot(
                snapshot_date=snap_date,
                category=cat,
                value=val,
                percentage=pct,
            )
        )

    db.commit()


# ---------------------------------------------------------------------------
# Dashboard page routes
# ---------------------------------------------------------------------------


class TestDashboardPages:
    def test_root_redirects_to_dashboard(self, client):
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/dashboard"

    def test_dashboard_empty_db(self, client):
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert b"dashboard" in resp.content.lower() or b"LinkedIn" in resp.content

    def test_dashboard_with_data(self, seeded_client):
        c, db = seeded_client
        _seed_db(db)
        resp = c.get("/dashboard")
        assert resp.status_code == 200

    def test_post_detail_not_found(self, client):
        resp = client.get("/dashboard/posts/99999")
        assert resp.status_code == 404

    def test_post_detail_found(self, seeded_client):
        c, db = seeded_client
        _seed_db(db)
        post = db.query(Post).first()
        resp = c.get(f"/dashboard/posts/{post.id}")
        assert resp.status_code == 200

    def test_audience_page_empty(self, client):
        resp = client.get("/dashboard/audience")
        assert resp.status_code == 200

    def test_audience_page_with_data(self, seeded_client):
        c, db = seeded_client
        _seed_db(db)
        resp = c.get("/dashboard/audience")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Upload routes
# ---------------------------------------------------------------------------


class TestUploadRoutes:
    def test_upload_form_renders(self, client):
        resp = client.get("/upload")
        assert resp.status_code == 200
        assert b"upload" in resp.content.lower()

    def test_upload_valid_xlsx(self, client, sample_xlsx_path):
        file_bytes = sample_xlsx_path.read_bytes()
        resp = client.post(
            "/upload",
            files={"file": ("export.xlsx", io.BytesIO(file_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            follow_redirects=False,
        )
        # Should redirect to dashboard on success
        assert resp.status_code == 303
        assert resp.headers["location"] == "/dashboard"

    def test_upload_duplicate_file_returns_409(self, client, sample_xlsx_path):
        file_bytes = sample_xlsx_path.read_bytes()
        # First upload
        client.post(
            "/upload",
            files={"file": ("export.xlsx", io.BytesIO(file_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            follow_redirects=False,
        )
        # Second upload of same content
        resp = client.post(
            "/upload",
            files={"file": ("export_copy.xlsx", io.BytesIO(file_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            follow_redirects=False,
        )
        assert resp.status_code == 409

    def test_upload_invalid_extension_returns_400(self, client):
        resp = client.post(
            "/upload",
            files={"file": ("data.txt", io.BytesIO(b"not a spreadsheet"), "text/plain")},
            follow_redirects=False,
        )
        assert resp.status_code == 400

    def test_upload_empty_file_returns_400(self, client):
        resp = client.post(
            "/upload",
            files={"file": ("empty.xlsx", io.BytesIO(b""), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            follow_redirects=False,
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# API: health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# API: metrics/summary
# ---------------------------------------------------------------------------


class TestMetricsSummary:
    def test_summary_empty_db(self, client):
        resp = client.get("/api/metrics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_impressions" in data
        assert "avg_engagement_rate" in data
        assert "total_followers" in data
        assert "total_posts_tracked" in data

    def test_summary_with_data(self, seeded_client):
        c, db = seeded_client
        _seed_db(db)
        resp = c.get("/api/metrics/summary?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_impressions"] > 0
        assert data["total_followers"] > 0


# ---------------------------------------------------------------------------
# API: metrics/timeseries
# ---------------------------------------------------------------------------


class TestMetricsTimeseries:
    def test_timeseries_empty_db(self, client):
        resp = client.get("/api/metrics/timeseries?metric=impressions&days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric"] == "impressions"
        assert isinstance(data["labels"], list)
        assert isinstance(data["values"], list)

    def test_timeseries_with_data(self, seeded_client):
        c, db = seeded_client
        _seed_db(db)
        resp = c.get("/api/metrics/timeseries?metric=impressions&days=60")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["labels"]) > 0

    def test_invalid_metric_rejected(self, client):
        resp = client.get("/api/metrics/timeseries?metric=invalid_field")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# API: posts
# ---------------------------------------------------------------------------


class TestPostsApi:
    def test_list_posts_empty(self, client):
        resp = client.get("/api/posts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["posts"] == []

    def test_list_posts_with_data(self, seeded_client):
        c, db = seeded_client
        _seed_db(db)
        resp = c.get("/api/posts?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["posts"]) == 5

    def test_list_posts_sorting(self, seeded_client):
        c, db = seeded_client
        _seed_db(db)
        resp = c.get("/api/posts?sort=impressions&order=desc")
        assert resp.status_code == 200
        data = resp.json()
        impressions = [p["impressions"] for p in data["posts"]]
        assert impressions == sorted(impressions, reverse=True)

    def test_get_single_post_not_found(self, client):
        resp = client.get("/api/posts/99999")
        assert resp.status_code == 404

    def test_get_single_post_found(self, seeded_client):
        c, db = seeded_client
        _seed_db(db)
        post = db.query(Post).first()
        resp = c.get(f"/api/posts/{post.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == post.id
        assert "daily_metrics" in data

    def test_invalid_sort_field_rejected(self, client):
        resp = client.get("/api/posts?sort=password")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# API: demographics
# ---------------------------------------------------------------------------


class TestDemographicsApi:
    def test_demographics_empty_db(self, client):
        resp = client.get("/api/demographics?category=industry")
        assert resp.status_code == 200
        data = resp.json()
        assert data["labels"] == []

    def test_demographics_with_data(self, seeded_client):
        c, db = seeded_client
        _seed_db(db)
        resp = c.get("/api/demographics?category=industry")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["labels"]) > 0

    def test_invalid_category_rejected(self, client):
        resp = client.get("/api/demographics?category=password")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# API: followers
# ---------------------------------------------------------------------------


class TestFollowersTrendApi:
    def test_trend_empty_db(self, client):
        resp = client.get("/api/followers/trend?days=90")
        assert resp.status_code == 200
        data = resp.json()
        assert data["labels"] == []

    def test_trend_with_data(self, seeded_client):
        c, db = seeded_client
        _seed_db(db)
        resp = c.get("/api/followers/trend?days=90")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["labels"]) == 30
        assert len(data["total_followers"]) == 30


# ---------------------------------------------------------------------------
# Cohort seed helper
# ---------------------------------------------------------------------------


def _seed_cohort_posts(db: Session) -> list[Post]:
    """Insert 6 posts with cohort metadata spanning two calendar months."""
    today = date.today()
    base = today - timedelta(days=80)
    cohort_data = [
        ("risk-management", "story",    "personal-story", "medium", 8,  2000, 80, 20, 10),
        ("risk-management", "listicle", "statistic",      "short",  9,  1800, 60, 12,  5),
        ("devsecops",       "tutorial", "how-to",         "long",   10, 3000, 90, 30, 15),
        ("devsecops",       "hot-take", "contrarian",     "short",  11, 1500, 50,  8,  3),
        ("htb-writeup",     "tutorial", "how-to",         "long",   14, 2500, 70, 18, 12),
        ("htb-writeup",     "story",    "personal-story", "medium", 15, 2200, 65, 14,  8),
    ]
    posts = []
    for i, (topic, fmt, hook, length, hour, impr, reac, comm, shar) in enumerate(
        cohort_data
    ):
        post = Post(
            post_date=base + timedelta(days=i * 10),
            title=f"Cohort post {i + 1}",
            post_type="text",
            impressions=impr,
            members_reached=int(impr * 0.8),
            reactions=reac,
            comments=comm,
            shares=shar,
            clicks=reac // 2,
            topic=topic,
            content_format=fmt,
            hook_style=hook,
            length_bucket=length,
            post_hour=hour,
        )
        post.recalculate_engagement_rate()
        db.add(post)
        posts.append(post)
    db.commit()
    for p in posts:
        db.refresh(p)
    return posts


# ---------------------------------------------------------------------------
# API: analytics/engagement
# ---------------------------------------------------------------------------


class TestAnalyticsEngagementApi:
    def test_engagement_empty_db(self, client):
        """Returns valid structure with empty data."""
        resp = client.get("/api/analytics/engagement")
        assert resp.status_code == 200
        data = resp.json()
        assert "posts" in data
        assert "monthly_medians" in data
        assert "top_10pct_threshold" in data
        assert "baseline" in data
        assert "last_30d" in data
        assert data["posts"] == []
        assert data["monthly_medians"] == []
        assert data["top_10pct_threshold"] == 0.0

    def test_engagement_with_data(self, seeded_client):
        """Returns posts, monthly_medians, threshold, baseline, last_30d."""
        c, db = seeded_client
        _seed_db(db)
        resp = c.get("/api/analytics/engagement?days=365")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["posts"]) == 5
        assert len(data["monthly_medians"]) >= 1
        assert data["top_10pct_threshold"] > 0.0
        assert data["baseline"]["post_count"] == 5
        # Each post object has required fields
        post = data["posts"][0]
        assert "id" in post
        assert "post_date" in post
        assert "engagement_rate" in post
        assert "weighted_score" in post
        assert "rolling_avg_5" in post

    def test_engagement_rolling_avg(self, seeded_client):
        """Rolling average is computed for a window of 5 posts."""
        c, db = seeded_client
        _seed_cohort_posts(db)
        resp = c.get("/api/analytics/engagement?days=365")
        assert resp.status_code == 200
        data = resp.json()
        posts = data["posts"]
        assert len(posts) == 6
        # The last post's rolling_avg_5 should differ from its own engagement_rate
        # (it averages over the 5-post window)
        last = posts[-1]
        assert last["rolling_avg_5"] != last["engagement_rate"] or len(posts) == 1

    def test_engagement_rolling_avg_few_posts(self, seeded_client):
        """Rolling average handles fewer than 5 posts gracefully."""
        c, db = seeded_client
        # Insert only 2 posts
        today = date.today()
        for i in range(2):
            post = Post(
                post_date=today - timedelta(days=i * 7),
                impressions=1000,
                reactions=50,
                comments=10,
                shares=5,
            )
            post.recalculate_engagement_rate()
            db.add(post)
        db.commit()
        resp = c.get("/api/analytics/engagement?days=365")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["posts"]) == 2
        # First post: rolling avg equals its own rate
        first = data["posts"][0]
        assert first["rolling_avg_5"] == pytest.approx(first["engagement_rate"], rel=1e-4)

    def test_engagement_weighted_score(self, seeded_client):
        """Weighted score matches manual calculation."""
        c, db = seeded_client
        post = Post(
            post_date=date.today() - timedelta(days=1),
            impressions=1000,
            reactions=50,
            comments=10,
            shares=5,
        )
        post.recalculate_engagement_rate()
        db.add(post)
        db.commit()
        resp = c.get("/api/analytics/engagement?days=365")
        assert resp.status_code == 200
        data = resp.json()
        p = data["posts"][0]
        # ((1*50) + (3*10) + (4*5)) / 1000 = 100 / 1000 = 0.1
        assert p["weighted_score"] == pytest.approx(0.1, rel=1e-4)

    def test_engagement_top_10pct_threshold(self, seeded_client):
        """Top 10% threshold is correct for known data."""
        c, db = seeded_client
        _seed_db(db)
        resp = c.get("/api/analytics/engagement?days=365")
        assert resp.status_code == 200
        data = resp.json()
        threshold = data["top_10pct_threshold"]
        rates = [p["engagement_rate"] for p in data["posts"]]
        assert threshold >= 0.0
        # Threshold should be >= the median engagement rate
        assert threshold >= sorted(rates)[len(rates) // 2]

    def test_engagement_invalid_days_rejected(self, client):
        """Days parameter outside valid range returns 422."""
        resp = client.get("/api/analytics/engagement?days=10")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# API: analytics/cohorts
# ---------------------------------------------------------------------------


class TestAnalyticsCohortApi:
    def test_cohorts_empty_db(self, client):
        """Returns valid structure with no cohorts."""
        resp = client.get("/api/analytics/cohorts?dimension=topic")
        assert resp.status_code == 200
        data = resp.json()
        assert data["dimension"] == "topic"
        assert data["cohorts"] == []

    def test_cohorts_by_topic(self, seeded_client):
        """Groups posts by topic correctly."""
        c, db = seeded_client
        _seed_cohort_posts(db)
        resp = c.get("/api/analytics/cohorts?dimension=topic")
        assert resp.status_code == 200
        data = resp.json()
        assert data["dimension"] == "topic"
        topics = {ch["value"] for ch in data["cohorts"]}
        assert "risk-management" in topics
        assert "devsecops" in topics
        assert "htb-writeup" in topics
        for cohort in data["cohorts"]:
            assert cohort["post_count"] == 2
            assert "avg_engagement_rate" in cohort
            assert "avg_weighted_score" in cohort
            assert "median_engagement_rate" in cohort
            assert "best_post_id" in cohort

    def test_cohorts_exclude_null(self, seeded_client):
        """Posts without the dimension set are excluded."""
        c, db = seeded_client
        # One post with topic, one without
        tagged = Post(
            post_date=date.today() - timedelta(days=10),
            impressions=1000,
            reactions=50,
            comments=10,
            shares=5,
            topic="devsecops",
        )
        tagged.recalculate_engagement_rate()
        untagged = Post(
            post_date=date.today() - timedelta(days=5),
            impressions=800,
            reactions=40,
            comments=8,
            shares=3,
        )
        untagged.recalculate_engagement_rate()
        db.add(tagged)
        db.add(untagged)
        db.commit()
        resp = c.get("/api/analytics/cohorts?dimension=topic")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["cohorts"]) == 1
        assert data["cohorts"][0]["post_count"] == 1

    def test_invalid_dimension_rejected(self, client):
        """Unknown dimension returns 422."""
        resp = client.get("/api/analytics/cohorts?dimension=password")
        assert resp.status_code == 422

    def test_cohorts_by_content_format(self, seeded_client):
        """Groups posts by content_format correctly."""
        c, db = seeded_client
        _seed_cohort_posts(db)
        resp = c.get("/api/analytics/cohorts?dimension=content_format")
        assert resp.status_code == 200
        data = resp.json()
        formats = {ch["value"] for ch in data["cohorts"]}
        assert "story" in formats
        assert "tutorial" in formats


# ---------------------------------------------------------------------------
# API: PATCH /api/posts/{id} cohort fields
# ---------------------------------------------------------------------------


class TestPostUpdateCohortFields:
    def test_update_topic(self, seeded_client):
        """PATCH with topic updates the field."""
        c, db = seeded_client
        _seed_db(db)
        post = db.query(Post).first()
        resp = c.patch(f"/api/posts/{post.id}?topic=risk-management")
        assert resp.status_code == 200
        data = resp.json()
        assert data["topic"] == "risk-management"

    def test_update_all_cohort_fields(self, seeded_client):
        """PATCH with all cohort fields updates them simultaneously."""
        c, db = seeded_client
        _seed_db(db)
        post = db.query(Post).first()
        params = (
            "topic=devsecops"
            "&content_format=story"
            "&hook_style=contrarian"
            "&length_bucket=medium"
            "&post_hour=9"
        )
        resp = c.patch(f"/api/posts/{post.id}?{params}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["topic"] == "devsecops"
        assert data["content_format"] == "story"
        assert data["hook_style"] == "contrarian"
        assert data["length_bucket"] == "medium"
        assert data["post_hour"] == 9

    def test_clear_cohort_field(self, seeded_client):
        """PATCH with empty string clears the field to null."""
        c, db = seeded_client
        _seed_db(db)
        post = db.query(Post).first()
        # First set a value
        c.patch(f"/api/posts/{post.id}?topic=risk-management")
        # Then clear it
        resp = c.patch(f"/api/posts/{post.id}?topic=")
        assert resp.status_code == 200
        data = resp.json()
        assert data["topic"] is None

    def test_topic_normalized_on_input(self, seeded_client):
        """Topic with mixed case and spaces is normalized to lowercase hyphenated form."""
        c, db = seeded_client
        _seed_db(db)
        post = db.query(Post).first()
        resp = c.patch(f"/api/posts/{post.id}?topic=Risk+Management")
        assert resp.status_code == 200
        data = resp.json()
        assert data["topic"] == "risk-management"


# ---------------------------------------------------------------------------
# Dashboard: analytics page route
# ---------------------------------------------------------------------------


class TestAnalyticsPage:
    def test_analytics_page_empty_db(self, client):
        """Page renders without error when the database is empty."""
        resp = client.get("/dashboard/analytics")
        assert resp.status_code == 200
        content = resp.content.lower()
        assert b"analytics" in content

    def test_analytics_page_with_data(self, seeded_client):
        """Page renders successfully when posts exist."""
        c, db = seeded_client
        _seed_db(db)
        resp = c.get("/dashboard/analytics")
        assert resp.status_code == 200
        assert resp.status_code == 200
