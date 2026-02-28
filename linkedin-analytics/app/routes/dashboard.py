"""Dashboard page routes: main view, post detail, audience."""

import logging
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import DailyMetric, DemographicSnapshot, FollowerSnapshot, Post, Upload

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/", response_class=RedirectResponse)
async def root() -> RedirectResponse:
    """Redirect root URL to the main dashboard."""
    return RedirectResponse(url="/dashboard", status_code=302)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    days: int = 30,
    db: Session = Depends(get_session),
) -> HTMLResponse:
    """Render the main dashboard with KPI cards and recent posts table."""
    cutoff = date.today() - timedelta(days=days)

    # KPI: total impressions in period (account-level daily metrics)
    total_impressions = (
        db.query(func.sum(DailyMetric.impressions))
        .filter(DailyMetric.post_id.is_(None), DailyMetric.metric_date >= cutoff)
        .scalar()
        or 0
    )

    # KPI: average engagement rate for posts in period
    avg_engagement = (
        db.query(func.avg(Post.engagement_rate))
        .filter(Post.post_date >= cutoff)
        .scalar()
        or 0.0
    )

    # KPI: current follower count
    latest_snapshot = (
        db.query(FollowerSnapshot)
        .order_by(desc(FollowerSnapshot.snapshot_date))
        .first()
    )
    total_followers = latest_snapshot.total_followers if latest_snapshot else 0

    # KPI: total posts tracked
    total_posts = db.query(func.count(Post.id)).scalar() or 0

    # Recent posts table (last 10 by date)
    recent_posts = (
        db.query(Post)
        .order_by(desc(Post.post_date))
        .limit(10)
        .all()
    )

    # Upload count for header badge
    upload_count = db.query(func.count(Upload.id)).scalar() or 0

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "days": days,
            "total_impressions": int(total_impressions),
            "avg_engagement_rate": round(float(avg_engagement) * 100, 2),
            "total_followers": int(total_followers),
            "total_posts": int(total_posts),
            "recent_posts": recent_posts,
            "upload_count": upload_count,
            "has_data": total_posts > 0,
        },
    )


@router.get("/dashboard/posts/{post_id}", response_class=HTMLResponse)
async def post_detail(
    post_id: int,
    request: Request,
    db: Session = Depends(get_session),
) -> HTMLResponse:
    """Render the post detail page for a single post.

    Args:
        post_id: Database ID of the post.

    Raises:
        HTTPException 404: If the post is not found.
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail=f"Post {post_id} not found.")

    daily_metrics = (
        db.query(DailyMetric)
        .filter(DailyMetric.post_id == post_id)
        .order_by(DailyMetric.metric_date)
        .all()
    )

    # Surrounding posts for navigation
    prev_post = (
        db.query(Post)
        .filter(Post.post_date < post.post_date)
        .order_by(desc(Post.post_date))
        .first()
    )
    next_post = (
        db.query(Post)
        .filter(Post.post_date > post.post_date)
        .order_by(Post.post_date)
        .first()
    )

    return templates.TemplateResponse(
        request,
        "post_detail.html",
        {
            "post": post,
            "daily_metrics": daily_metrics,
            "prev_post": prev_post,
            "next_post": next_post,
        },
    )


@router.get("/dashboard/analytics", response_class=HTMLResponse)
async def analytics(
    request: Request,
    db: Session = Depends(get_session),
) -> HTMLResponse:
    """Render the engagement analytics page."""
    total_posts = db.query(func.count(Post.id)).scalar() or 0
    return templates.TemplateResponse(
        request,
        "analytics.html",
        {
            "has_data": total_posts > 0,
        },
    )


@router.get("/dashboard/audience", response_class=HTMLResponse)
async def audience(
    request: Request,
    db: Session = Depends(get_session),
) -> HTMLResponse:
    """Render the audience demographics page."""
    # Latest follower trend (90 days)
    cutoff = date.today() - timedelta(days=90)
    follower_trend = (
        db.query(FollowerSnapshot)
        .filter(FollowerSnapshot.snapshot_date >= cutoff)
        .order_by(FollowerSnapshot.snapshot_date)
        .all()
    )

    # Latest demographic snapshot date
    latest_demo_date = (
        db.query(func.max(DemographicSnapshot.snapshot_date)).scalar()
    )

    demographics: dict[str, list] = {}
    if latest_demo_date:
        for category in ("industry", "job_title", "seniority", "location"):
            rows = (
                db.query(DemographicSnapshot)
                .filter(
                    DemographicSnapshot.category == category,
                    DemographicSnapshot.snapshot_date == latest_demo_date,
                )
                .order_by(desc(DemographicSnapshot.percentage))
                .limit(10)
                .all()
            )
            # Convert decimal percentages (0.40) to display percentages (40.0)
            for row in rows:
                row.percentage = round(row.percentage * 100, 1)
            demographics[category] = rows

    return templates.TemplateResponse(
        request,
        "audience.html",
        {
            "follower_trend": follower_trend,
            "demographics": demographics,
            "latest_demo_date": latest_demo_date,
            "has_data": bool(follower_trend or latest_demo_date),
        },
    )
