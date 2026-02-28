"""JSON API routes for chart data and dashboard metrics."""

import logging
import sqlite3
import tempfile
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_session
from app.models import DailyMetric, DemographicSnapshot, FollowerSnapshot, Post, Upload

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for Docker and load balancers."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Summary / KPI
# ---------------------------------------------------------------------------


@router.get("/api/metrics/summary")
async def metrics_summary(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return KPI summary metrics for the dashboard header cards.

    Args:
        days: Lookback window in days (default 30).

    Returns:
        JSON with total_impressions, avg_engagement_rate, total_followers,
        total_posts_tracked, and new_followers_period.
    """
    cutoff = date.today() - timedelta(days=days)

    # Total impressions (from daily account-level metrics, post_id=None)
    total_impressions = (
        db.query(func.sum(DailyMetric.impressions))
        .filter(DailyMetric.post_id.is_(None), DailyMetric.metric_date >= cutoff)
        .scalar()
        or 0
    )

    # Average engagement rate across posts in the period
    avg_engagement = (
        db.query(func.avg(Post.engagement_rate))
        .filter(Post.post_date >= cutoff)
        .scalar()
        or 0.0
    )

    # Latest follower count
    latest_snapshot = (
        db.query(FollowerSnapshot)
        .order_by(desc(FollowerSnapshot.snapshot_date))
        .first()
    )
    total_followers = latest_snapshot.total_followers if latest_snapshot else 0

    # New followers in period
    new_followers = (
        db.query(func.sum(FollowerSnapshot.new_followers))
        .filter(FollowerSnapshot.snapshot_date >= cutoff)
        .scalar()
        or 0
    )

    # Total posts tracked
    total_posts = db.query(func.count(Post.id)).scalar() or 0

    return {
        "total_impressions": int(total_impressions),
        "avg_engagement_rate": round(float(avg_engagement), 4),
        "total_followers": int(total_followers),
        "new_followers_period": int(new_followers),
        "total_posts_tracked": int(total_posts),
        "period_days": days,
    }


# ---------------------------------------------------------------------------
# Time series
# ---------------------------------------------------------------------------


@router.get("/api/metrics/timeseries")
async def metrics_timeseries(
    metric: str = Query("impressions", pattern="^(impressions|members_reached|reactions|comments|shares|clicks)$"),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return daily time series data for a given metric.

    Args:
        metric: Metric name to return (impressions, members_reached, etc.).
        days: Number of days to look back (default 30).

    Returns:
        JSON with labels (dates) and values arrays for Chart.js.
    """
    cutoff = date.today() - timedelta(days=days)

    # Map metric name to column
    column_map = {
        "impressions": DailyMetric.impressions,
        "members_reached": DailyMetric.members_reached,
        "reactions": DailyMetric.reactions,
        "comments": DailyMetric.comments,
        "shares": DailyMetric.shares,
        "clicks": DailyMetric.clicks,
    }
    col = column_map[metric]

    rows = (
        db.query(DailyMetric.metric_date, func.sum(col).label("value"))
        .filter(DailyMetric.post_id.is_(None), DailyMetric.metric_date >= cutoff)
        .group_by(DailyMetric.metric_date)
        .order_by(DailyMetric.metric_date)
        .all()
    )

    labels = [str(r.metric_date) for r in rows]
    values = [int(r.value or 0) for r in rows]

    return {
        "metric": metric,
        "period_days": days,
        "labels": labels,
        "values": values,
    }


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------


@router.get("/api/posts")
async def list_posts(
    sort: str = Query("post_date", pattern="^(post_date|impressions|engagement_rate|reactions|comments|shares|clicks)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return a paginated, sorted list of posts.

    Args:
        sort: Field to sort by.
        order: Sort direction (asc or desc).
        limit: Maximum number of results.
        offset: Number of records to skip.

    Returns:
        JSON with total count and list of post objects.
    """
    sort_map = {
        "post_date": Post.post_date,
        "impressions": Post.impressions,
        "engagement_rate": Post.engagement_rate,
        "reactions": Post.reactions,
        "comments": Post.comments,
        "shares": Post.shares,
        "clicks": Post.clicks,
    }
    sort_col = sort_map[sort]
    sort_expr = desc(sort_col) if order == "desc" else sort_col

    total = db.query(func.count(Post.id)).scalar() or 0
    posts = (
        db.query(Post)
        .order_by(sort_expr)
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "posts": [_serialize_post(p) for p in posts],
    }


@router.get("/api/posts/{post_id}")
async def get_post(
    post_id: int,
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return metrics for a single post.

    Args:
        post_id: Post database ID.

    Returns:
        JSON with all post fields and daily metrics if available.

    Raises:
        HTTPException 404: If the post is not found.
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail=f"Post {post_id} not found.")

    daily = (
        db.query(DailyMetric)
        .filter(DailyMetric.post_id == post_id)
        .order_by(DailyMetric.metric_date)
        .all()
    )

    data = _serialize_post(post)
    data["daily_metrics"] = [
        {
            "date": str(m.metric_date),
            "impressions": m.impressions,
            "reactions": m.reactions,
            "comments": m.comments,
            "shares": m.shares,
            "clicks": m.clicks,
        }
        for m in daily
    ]
    return data


def _serialize_post(post: Post) -> dict[str, Any]:
    return {
        "id": post.id,
        "linkedin_post_id": post.linkedin_post_id,
        "title": post.title,
        "post_date": str(post.post_date),
        "post_type": post.post_type,
        "impressions": post.impressions,
        "members_reached": post.members_reached,
        "reactions": post.reactions,
        "comments": post.comments,
        "shares": post.shares,
        "clicks": post.clicks,
        "engagement_rate": round(post.engagement_rate or 0.0, 4),
    }


# ---------------------------------------------------------------------------
# Demographics
# ---------------------------------------------------------------------------


@router.get("/api/demographics")
async def get_demographics(
    category: str = Query("industry", pattern="^(industry|job_title|seniority|location)$"),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return demographic breakdown for a given audience category.

    Args:
        category: One of industry, job_title, seniority, location.

    Returns:
        JSON with labels and values arrays for Chart.js.
    """
    # Use the most recent snapshot date for this category
    latest_date = (
        db.query(func.max(DemographicSnapshot.snapshot_date))
        .filter(DemographicSnapshot.category == category)
        .scalar()
    )

    if not latest_date:
        return {"category": category, "snapshot_date": None, "labels": [], "values": []}

    rows = (
        db.query(DemographicSnapshot)
        .filter(
            DemographicSnapshot.category == category,
            DemographicSnapshot.snapshot_date == latest_date,
        )
        .order_by(desc(DemographicSnapshot.percentage))
        .all()
    )

    return {
        "category": category,
        "snapshot_date": str(latest_date),
        "labels": [r.value for r in rows],
        "values": [round(r.percentage * 100, 1) for r in rows],
    }


# ---------------------------------------------------------------------------
# Followers
# ---------------------------------------------------------------------------


@router.get("/api/followers/trend")
async def followers_trend(
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return follower growth trend data.

    Args:
        days: Number of days to look back (default 90).

    Returns:
        JSON with labels (dates) and total/new follower values.
    """
    cutoff = date.today() - timedelta(days=days)

    rows = (
        db.query(FollowerSnapshot)
        .filter(FollowerSnapshot.snapshot_date >= cutoff)
        .order_by(FollowerSnapshot.snapshot_date)
        .all()
    )

    return {
        "period_days": days,
        "labels": [str(r.snapshot_date) for r in rows],
        "total_followers": [r.total_followers for r in rows],
        "new_followers": [r.new_followers for r in rows],
    }


# ---------------------------------------------------------------------------
# Post update (draft linking)
# ---------------------------------------------------------------------------


@router.patch("/api/posts/{post_id}")
async def update_post(
    post_id: int,
    draft_id: str = Query(None, max_length=20),
    title: str = Query(None, max_length=100),
    db: Session = Depends(get_session),
):
    """Update a post's draft_id or title.

    Used to link dashboard posts to draft files in the bksp.ca repo.
    """
    post = db.query(Post).filter_by(id=post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if draft_id is not None:
        post.draft_id = draft_id if draft_id else None
    if title is not None:
        post.title = title if title else None

    db.commit()
    db.refresh(post)

    return {
        "id": post.id,
        "draft_id": post.draft_id,
        "title": post.title,
        "display_title": post.display_title,
    }


# ---------------------------------------------------------------------------
# Database export
# ---------------------------------------------------------------------------


@router.get("/api/export/db")
async def export_db() -> FileResponse:
    """Download a consistent snapshot of the SQLite database.

    Uses the SQLite Online Backup API (sqlite3.connect().backup()) to
    produce a point-in-time copy of the database. This ensures the
    downloaded file is internally consistent even when WAL mode is active
    and writes are in progress. The temporary snapshot is deleted after
    the response is sent.

    Returns:
        A consistent SQLite snapshot as a downloadable attachment.

    Raises:
        HTTPException 404: If the database file does not exist yet.
    """
    db_path = settings.db_path
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database file not found.")

    # Write the snapshot alongside the source file to stay on the same
    # filesystem (avoids cross-device rename issues) and use a unique name
    # so concurrent export requests do not collide.
    snapshot_path = db_path.parent / f"linkedin-export-{uuid.uuid4().hex}.db"
    try:
        src = sqlite3.connect(str(db_path))
        dst = sqlite3.connect(str(snapshot_path))
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
    except Exception as exc:
        snapshot_path.unlink(missing_ok=True)
        logger.error("Failed to create database snapshot for export: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create database snapshot.") from exc

    # background=True is not available on FileResponse; use a plain
    # FileResponse and rely on the OS to reclaim the file after the
    # response is fully sent. We schedule cleanup via a background task
    # by returning a custom subclass that removes the file on close.
    return FileResponse(
        path=str(snapshot_path),
        media_type="application/octet-stream",
        filename="linkedin.db",
        background=_delete_file_task(snapshot_path),
    )


def _delete_file_task(path: Path):
    """Return a BackgroundTask that deletes the given file."""
    from starlette.background import BackgroundTask

    def _delete():
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not remove export snapshot '%s': %s", path, exc)

    return BackgroundTask(_delete)
