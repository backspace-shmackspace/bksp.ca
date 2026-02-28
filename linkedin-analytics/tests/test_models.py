"""Tests for SQLAlchemy models."""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import DailyMetric, DemographicSnapshot, FollowerSnapshot, Post, Upload


class TestPostModel:
    """Tests for the Post model."""

    def test_create_minimal_post(self, test_session):
        post = Post(post_date=date(2025, 11, 1))
        test_session.add(post)
        test_session.commit()
        assert post.id is not None
        assert post.impressions == 0
        assert post.engagement_rate == 0.0

    def test_create_full_post(self, test_session):
        post = Post(
            post_date=date(2025, 11, 1),
            title="Test post about security patterns",
            post_type="text",
            impressions=1000,
            members_reached=800,
            reactions=50,
            comments=10,
            shares=5,
            clicks=20,
        )
        post.recalculate_engagement_rate()
        test_session.add(post)
        test_session.commit()

        assert post.id is not None
        assert post.title == "Test post about security patterns"
        assert post.engagement_rate == pytest.approx(0.065, rel=1e-3)

    def test_engagement_rate_calculation(self, test_session):
        post = Post(
            post_date=date(2025, 11, 1),
            impressions=1000,
            reactions=50,
            comments=10,
            shares=5,
        )
        post.recalculate_engagement_rate()
        # (50 + 10 + 5) / 1000 = 0.065
        assert post.engagement_rate == pytest.approx(0.065, rel=1e-3)

    def test_engagement_rate_zero_impressions(self, test_session):
        post = Post(post_date=date(2025, 11, 1), impressions=0, reactions=10)
        post.recalculate_engagement_rate()
        assert post.engagement_rate == 0.0

    def test_linkedin_post_id_unique_constraint(self, test_session):
        post1 = Post(post_date=date(2025, 11, 1), linkedin_post_id="abc123")
        post2 = Post(post_date=date(2025, 11, 2), linkedin_post_id="abc123")
        test_session.add(post1)
        test_session.commit()
        test_session.add(post2)
        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_query_posts(self, test_session, sample_posts):
        posts = test_session.query(Post).all()
        assert len(posts) == 5

    def test_post_repr(self, test_session):
        post = Post(post_date=date(2025, 11, 1), impressions=500)
        test_session.add(post)
        test_session.commit()
        repr_str = repr(post)
        assert "Post" in repr_str
        assert "2025-11-01" in repr_str

    def test_weighted_score_calculation(self, test_session):
        """Weighted score formula: ((1*reactions) + (3*comments) + (4*shares)) / impressions."""
        post = Post(
            post_date=date(2025, 11, 1),
            impressions=1000,
            reactions=50,
            comments=10,
            shares=5,
        )
        # ((1*50) + (3*10) + (4*5)) / 1000 = (50 + 30 + 20) / 1000 = 0.1
        assert post.weighted_score == pytest.approx(0.1, rel=1e-6)

    def test_weighted_score_zero_impressions(self, test_session):
        """Returns 0.0 when impressions is 0."""
        post = Post(post_date=date(2025, 11, 1), impressions=0, reactions=10)
        assert post.weighted_score == 0.0

    def test_weighted_score_none_impressions(self, test_session):
        """Returns 0.0 when impressions is None."""
        post = Post(post_date=date(2025, 11, 1))
        post.impressions = None
        assert post.weighted_score == 0.0

    def test_cohort_fields_nullable(self, test_session):
        """All cohort columns accept null values (default state)."""
        post = Post(post_date=date(2025, 11, 1))
        test_session.add(post)
        test_session.commit()
        test_session.refresh(post)
        assert post.topic is None
        assert post.content_format is None
        assert post.hook_style is None
        assert post.length_bucket is None
        assert post.post_hour is None

    def test_cohort_fields_persist(self, test_session):
        """Set and retrieve topic, content_format, hook_style, length_bucket, post_hour."""
        post = Post(
            post_date=date(2025, 11, 1),
            topic="risk-management",
            content_format="story",
            hook_style="personal-story",
            length_bucket="medium",
            post_hour=9,
        )
        test_session.add(post)
        test_session.commit()
        test_session.refresh(post)

        assert post.topic == "risk-management"
        assert post.content_format == "story"
        assert post.hook_style == "personal-story"
        assert post.length_bucket == "medium"
        assert post.post_hour == 9


class TestDailyMetricModel:
    """Tests for the DailyMetric model."""

    def test_create_daily_metric(self, test_session):
        metric = DailyMetric(
            post_id=None,
            metric_date=date(2025, 11, 1),
            impressions=500,
        )
        test_session.add(metric)
        test_session.commit()
        assert metric.id is not None

    def test_unique_constraint_post_date_with_post_id(self, test_session, sample_posts):
        """Unique constraint enforces (post_id, metric_date) when post_id is not NULL."""
        post = sample_posts[0]
        m1 = DailyMetric(post_id=post.id, metric_date=date(2025, 11, 1), impressions=100)
        m2 = DailyMetric(post_id=post.id, metric_date=date(2025, 11, 1), impressions=200)
        test_session.add(m1)
        test_session.commit()
        test_session.add(m2)
        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_account_level_metrics_allow_multiple_null_post_id(self, test_session):
        """SQLite treats NULL != NULL in UNIQUE constraints, so account-level
        (post_id=None) records on different dates are distinct rows."""
        m1 = DailyMetric(post_id=None, metric_date=date(2025, 11, 1), impressions=100)
        m2 = DailyMetric(post_id=None, metric_date=date(2025, 11, 2), impressions=200)
        test_session.add(m1)
        test_session.add(m2)
        test_session.commit()
        count = test_session.query(DailyMetric).count()
        assert count == 2

    def test_cascade_delete_from_post(self, test_session, sample_posts):
        post = sample_posts[0]
        metric = DailyMetric(
            post_id=post.id,
            metric_date=date(2025, 11, 1),
            impressions=200,
        )
        test_session.add(metric)
        test_session.commit()

        test_session.delete(post)
        test_session.commit()

        remaining = test_session.query(DailyMetric).filter_by(post_id=post.id).count()
        assert remaining == 0

    def test_daily_metric_repr(self, test_session):
        metric = DailyMetric(post_id=None, metric_date=date(2025, 11, 1))
        test_session.add(metric)
        test_session.commit()
        assert "DailyMetric" in repr(metric)


class TestFollowerSnapshotModel:
    """Tests for the FollowerSnapshot model."""

    def test_create_follower_snapshot(self, test_session):
        snap = FollowerSnapshot(
            snapshot_date=date(2025, 11, 1),
            total_followers=500,
            new_followers=5,
        )
        test_session.add(snap)
        test_session.commit()
        assert snap.id is not None

    def test_unique_date_constraint(self, test_session):
        snap1 = FollowerSnapshot(snapshot_date=date(2025, 11, 1), total_followers=500)
        snap2 = FollowerSnapshot(snapshot_date=date(2025, 11, 1), total_followers=510)
        test_session.add(snap1)
        test_session.commit()
        test_session.add(snap2)
        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_query_follower_snapshots(self, test_session, sample_follower_snapshots):
        snaps = test_session.query(FollowerSnapshot).all()
        assert len(snaps) == 30
        # First day starts at 450, subsequent days accumulate new followers
        for snap in snaps:
            assert snap.total_followers >= 450

    def test_follower_snapshot_repr(self, test_session):
        snap = FollowerSnapshot(snapshot_date=date(2025, 11, 1), total_followers=500)
        test_session.add(snap)
        test_session.commit()
        assert "FollowerSnapshot" in repr(snap)


class TestDemographicSnapshotModel:
    """Tests for the DemographicSnapshot model."""

    def test_create_demographic_snapshot(self, test_session):
        demo = DemographicSnapshot(
            snapshot_date=date(2025, 11, 30),
            category="industry",
            value="Information Technology",
            percentage=32.5,
        )
        test_session.add(demo)
        test_session.commit()
        assert demo.id is not None

    def test_unique_constraint(self, test_session):
        d1 = DemographicSnapshot(
            snapshot_date=date(2025, 11, 30),
            category="industry",
            value="IT",
            percentage=30.0,
        )
        d2 = DemographicSnapshot(
            snapshot_date=date(2025, 11, 30),
            category="industry",
            value="IT",
            percentage=31.0,
        )
        test_session.add(d1)
        test_session.commit()
        test_session.add(d2)
        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_query_demographics(self, test_session, sample_demographics):
        demos = test_session.query(DemographicSnapshot).all()
        assert len(demos) == 9

        industries = (
            test_session.query(DemographicSnapshot)
            .filter_by(category="industry")
            .all()
        )
        assert len(industries) == 3

    def test_demographic_repr(self, test_session):
        demo = DemographicSnapshot(
            snapshot_date=date(2025, 11, 30),
            category="seniority",
            value="Senior",
            percentage=40.0,
        )
        test_session.add(demo)
        test_session.commit()
        assert "DemographicSnapshot" in repr(demo)


class TestUploadModel:
    """Tests for the Upload model."""

    def test_create_upload(self, test_session):
        upload = Upload(
            filename="linkedin_export_2025_11.xlsx",
            file_hash="abc" * 21 + "ab",
            records_imported=50,
            status="completed",
        )
        test_session.add(upload)
        test_session.commit()
        assert upload.id is not None
        assert upload.status == "completed"

    def test_unique_hash_constraint(self, test_session):
        u1 = Upload(filename="file1.xlsx", file_hash="deadbeef" * 8, records_imported=10)
        u2 = Upload(filename="file2.xlsx", file_hash="deadbeef" * 8, records_imported=20)
        test_session.add(u1)
        test_session.commit()
        test_session.add(u2)
        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_upload_repr(self, test_session):
        upload = Upload(
            filename="export.xlsx",
            file_hash="a1b2c3" * 10 + "a1b2",
            status="completed",
        )
        test_session.add(upload)
        test_session.commit()
        assert "Upload" in repr(upload)
