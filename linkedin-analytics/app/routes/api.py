"""JSON API routes for chart data and dashboard metrics."""

import hashlib
import logging
import math
import re as _re
import sqlite3
import statistics
import time
import uuid
from collections import OrderedDict, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_session
from app.models import DailyMetric, DemographicSnapshot, FollowerSnapshot, Post, PostDemographic, Upload

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

    data = _serialize_post(post, include_full_content=True)
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

    # Include per-post demographics if available
    post_demographics = (
        db.query(PostDemographic)
        .filter(PostDemographic.post_id == post_id)
        .order_by(PostDemographic.category, PostDemographic.percentage.desc())
        .all()
    )
    data["demographics"] = [
        {
            "category": d.category,
            "value": d.value,
            "percentage": round(d.percentage * 100, 1),
        }
        for d in post_demographics
    ]

    return data


def _serialize_post(post: Post, include_full_content: bool = False) -> dict[str, Any]:
    content = post.content
    if content and not include_full_content and len(content) > 200:
        content_preview = content[:200] + "..."
    else:
        content_preview = content

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
        "weighted_score": round(post.weighted_score, 6),
        "topic": post.topic,
        "content_format": post.content_format,
        "hook_style": post.hook_style,
        "length_bucket": post.length_bucket,
        "post_hour": post.post_hour,
        "content": content_preview,
        "status": post.status,
        "saves": post.saves,
        "sends": post.sends,
        "profile_views": post.profile_views,
        "followers_gained": post.followers_gained,
        "reposts": post.reposts,
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
    impressions: int = Query(None, ge=0),
    reactions: int = Query(None, ge=0),
    comments: int = Query(None, ge=0),
    shares: int = Query(None, ge=0),
    clicks: int = Query(None, ge=0),
    topic: str = Query(None, max_length=50),
    content_format: str = Query(None, max_length=30),
    hook_style: str = Query(None, max_length=30),
    length_bucket: str = Query(None, max_length=20),
    post_hour: int = Query(None, ge=0, le=23),
    content: str | None = Body(None),
    status: str | None = Query(None, pattern="^(draft|published|analytics_linked)$"),
    db: Session = Depends(get_session),
):
    """Update a post's metadata or metrics.

    Used to link dashboard posts to draft files and to correct metrics
    with actual lifetime values from LinkedIn's in-app analytics (the
    export only captures metrics within its date range window).

    String cohort fields (topic, content_format, hook_style, length_bucket)
    are normalized on input: lowercased, stripped, spaces replaced with hyphens.
    Empty strings are stored as null to prevent cohort fragmentation.
    """
    post = db.query(Post).filter_by(id=post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if draft_id is not None:
        post.draft_id = draft_id if draft_id else None
    if title is not None:
        post.title = title if title else None
    if impressions is not None:
        post.impressions = impressions
    if reactions is not None:
        post.reactions = reactions
    if comments is not None:
        post.comments = comments
    if shares is not None:
        post.shares = shares
    if clicks is not None:
        post.clicks = clicks
    if topic is not None:
        post.topic = _normalize_cohort_value(topic)
    if content_format is not None:
        post.content_format = _normalize_cohort_value(content_format)
    if hook_style is not None:
        post.hook_style = _normalize_cohort_value(hook_style)
    if length_bucket is not None:
        post.length_bucket = _normalize_cohort_value(length_bucket)
    if post_hour is not None:
        post.post_hour = post_hour
    if content is not None:
        post.content = content if content else None
    if status is not None:
        post.status = status

    post.recalculate_engagement_rate()
    db.commit()
    db.refresh(post)

    return {
        "id": post.id,
        "draft_id": post.draft_id,
        "title": post.title,
        "display_title": post.display_title,
        "impressions": post.impressions,
        "reactions": post.reactions,
        "comments": post.comments,
        "shares": post.shares,
        "clicks": post.clicks,
        "engagement_rate": post.engagement_rate,
        "weighted_score": post.weighted_score,
        "topic": post.topic,
        "content_format": post.content_format,
        "hook_style": post.hook_style,
        "length_bucket": post.length_bucket,
        "post_hour": post.post_hour,
        "content": post.content,
        "status": post.status,
    }


# ---------------------------------------------------------------------------
# Cohort / analytics helpers
# ---------------------------------------------------------------------------


def _normalize_cohort_value(value: str) -> str | None:
    """Normalize a cohort string field for storage.

    Lowercases, strips leading/trailing whitespace, and replaces internal
    spaces with hyphens. Returns None for empty strings so that blank
    submissions clear the field rather than storing an empty string.
    """
    normalized = value.strip().lower().replace(" ", "-")
    return normalized if normalized else None


def _compute_rolling_avg(posts: list[Post], window: int = 5) -> list[float]:
    """Compute rolling average of engagement_rate over a sorted list of posts.

    For the first N posts where N < window, averages over all available posts
    up to that point.
    """
    result = []
    for i, post in enumerate(posts):
        start = max(0, i - window + 1)
        window_posts = posts[start : i + 1]
        avg = sum((p.engagement_rate or 0.0) for p in window_posts) / len(window_posts)
        result.append(round(avg, 6))
    return result


def _compute_top_10pct_threshold(engagement_rates: list[float]) -> float:
    """Return the engagement rate at the 90th percentile (top 10% threshold)."""
    if not engagement_rates:
        return 0.0
    sorted_rates = sorted(engagement_rates)
    idx = math.ceil(len(sorted_rates) * 0.9) - 1
    return sorted_rates[max(0, idx)]


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


# ---------------------------------------------------------------------------
# Analytics endpoints
# ---------------------------------------------------------------------------


@router.get("/api/analytics/engagement")
async def analytics_engagement(
    days: int = Query(365, ge=30, le=1825),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return engagement rate time series, rolling average, monthly medians,
    top 10% threshold, and baseline vs last 30 days comparison.

    Args:
        days: Lookback window in days (default 365, min 30, max 1825).

    Returns:
        JSON with posts, monthly_medians, top_10pct_threshold, baseline,
        last_30d, and period_days.
    """
    cutoff = date.today() - timedelta(days=days)
    last_30d_cutoff = date.today() - timedelta(days=30)

    all_posts = (
        db.query(Post)
        .filter(Post.post_date >= cutoff)
        .order_by(Post.post_date)
        .all()
    )

    rolling_avgs = _compute_rolling_avg(all_posts)
    engagement_rates = [p.engagement_rate or 0.0 for p in all_posts]
    threshold = _compute_top_10pct_threshold(engagement_rates)
    monthly_medians = _compute_monthly_medians(all_posts)

    # Baseline: all posts in lookback window
    baseline_posts = all_posts
    baseline_count = len(baseline_posts)
    if baseline_count > 0:
        baseline_avg_er = round(
            sum(p.engagement_rate or 0.0 for p in baseline_posts) / baseline_count, 6
        )
        baseline_avg_ws = round(
            sum(p.weighted_score for p in baseline_posts) / baseline_count, 6
        )
    else:
        baseline_avg_er = 0.0
        baseline_avg_ws = 0.0

    # Last 30 days
    last_30d_posts = [p for p in all_posts if p.post_date >= last_30d_cutoff]
    last_30d_count = len(last_30d_posts)
    if last_30d_count > 0:
        last_30d_avg_er = round(
            sum(p.engagement_rate or 0.0 for p in last_30d_posts) / last_30d_count, 6
        )
        last_30d_avg_ws = round(
            sum(p.weighted_score for p in last_30d_posts) / last_30d_count, 6
        )
    else:
        last_30d_avg_er = 0.0
        last_30d_avg_ws = 0.0

    post_data = [
        {
            "id": p.id,
            "post_date": str(p.post_date),
            "title": p.display_title,
            "engagement_rate": round(p.engagement_rate or 0.0, 6),
            "weighted_score": round(p.weighted_score, 6),
            "rolling_avg_5": rolling_avgs[i],
            "impressions": p.impressions,
            "reactions": p.reactions,
            "comments": p.comments,
            "shares": p.shares,
        }
        for i, p in enumerate(all_posts)
    ]

    return {
        "posts": post_data,
        "monthly_medians": monthly_medians,
        "top_10pct_threshold": round(threshold, 6),
        "baseline": {
            "avg_engagement_rate": baseline_avg_er,
            "avg_weighted_score": baseline_avg_ws,
            "post_count": baseline_count,
        },
        "last_30d": {
            "avg_engagement_rate": last_30d_avg_er,
            "avg_weighted_score": last_30d_avg_ws,
            "post_count": last_30d_count,
        },
        "period_days": days,
    }


@router.get("/api/analytics/cohorts")
async def analytics_cohorts(
    dimension: str = Query(
        ...,
        pattern="^(topic|content_format|hook_style|length_bucket|post_hour)$",
    ),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return engagement metrics grouped by a cohort dimension.

    Only posts with the requested dimension populated are included.
    Posts with null values for the dimension are excluded.

    Args:
        dimension: One of topic, content_format, hook_style, length_bucket, post_hour.

    Returns:
        JSON with dimension name and list of per-cohort stats.
    """
    # Map dimension name to the Post column attribute
    dimension_map = {
        "topic": Post.topic,
        "content_format": Post.content_format,
        "hook_style": Post.hook_style,
        "length_bucket": Post.length_bucket,
        "post_hour": Post.post_hour,
    }
    col = dimension_map[dimension]

    posts = (
        db.query(Post)
        .filter(col.isnot(None))
        .order_by(Post.post_date)
        .all()
    )

    # Group by dimension value
    by_value: dict[str, list[Post]] = defaultdict(list)
    for p in posts:
        key = str(getattr(p, dimension))
        by_value[key].append(p)

    cohorts = []
    for value, group in sorted(by_value.items()):
        er_values = [p.engagement_rate or 0.0 for p in group]
        ws_values = [p.weighted_score for p in group]
        avg_er = round(sum(er_values) / len(er_values), 6)
        avg_ws = round(sum(ws_values) / len(ws_values), 6)
        median_er = round(statistics.median(er_values), 6)

        # Best post: highest engagement_rate in this cohort
        best_post = max(group, key=lambda p: p.engagement_rate or 0.0)

        cohorts.append(
            {
                "value": value,
                "post_count": len(group),
                "avg_engagement_rate": avg_er,
                "avg_weighted_score": avg_ws,
                "median_engagement_rate": median_er,
                "best_post_id": best_post.id,
                "best_post_title": best_post.display_title,
            }
        )

    return {"dimension": dimension, "cohorts": cohorts}


# ---------------------------------------------------------------------------
# Draft file reader helpers
# ---------------------------------------------------------------------------


def _strip_frontmatter(text: str) -> str:
    """Strip YAML frontmatter from markdown content.

    Removes the leading --- delimited YAML block if present.
    Draft files from the content pipeline may have frontmatter that
    should not be published to LinkedIn.
    """
    stripped = _re.sub(
        r"\A---\s*\n.*?\n---\s*\n",
        "",
        text,
        count=1,
        flags=_re.DOTALL,
    )
    return stripped.lstrip()


def list_draft_files() -> list[dict[str, Any]]:
    """List LinkedIn draft files from the configured drafts directory.

    Returns a list of dicts with keys: draft_id, filename, path, title.
    Filters out review/supplementary files (*.copy-review.md, etc.).
    """
    drafts_dir = settings.drafts_dir
    if not drafts_dir.exists():
        return []

    exclude_suffixes = {
        ".copy-review.md",
        ".sensitivity-review.md",
        ".review-summary.md",
        ".visual-specs.md",
    }

    drafts: list[dict[str, Any]] = []
    for f in sorted(drafts_dir.glob("*.md")):
        if any(f.name.endswith(suffix) for suffix in exclude_suffixes):
            continue

        parts = f.stem.split("-", 1)
        draft_id = parts[0] if parts[0].isdigit() else None
        title = parts[1].replace("-", " ").title() if len(parts) > 1 else f.stem

        drafts.append({
            "draft_id": draft_id,
            "filename": f.name,
            "path": str(f),
            "title": title,
        })

    return drafts


def read_draft_file(filename: str) -> str | None:
    """Read a draft file's content with frontmatter stripped.

    Returns None if not found or if path traversal is detected.
    Only reads files from the configured drafts directory.

    Args:
        filename: Bare filename (no directory components).

    Returns:
        Frontmatter-stripped file content, or None if inaccessible.
    """
    drafts_dir = settings.drafts_dir
    target = (drafts_dir / filename).resolve()
    try:
        if not target.is_relative_to(drafts_dir.resolve()):
            return None
    except ValueError:
        return None
    if not target.exists():
        return None
    raw = target.read_text(encoding="utf-8")
    return _strip_frontmatter(raw)


# ---------------------------------------------------------------------------
# Drafts API endpoints
# ---------------------------------------------------------------------------


@router.get("/api/drafts")
async def list_drafts() -> dict[str, Any]:
    """List LinkedIn draft files from the drafts directory.

    Returns:
        JSON with list of draft objects (draft_id, filename, title, path).
    """
    drafts = list_draft_files()
    return {"drafts": drafts, "count": len(drafts)}


@router.get("/api/drafts/{filename}")
async def get_draft(filename: str) -> dict[str, Any]:
    """Read a draft file's content (frontmatter stripped).

    Path traversal is prevented by resolving the path and checking
    it is within the configured drafts directory using Path.is_relative_to().

    Args:
        filename: Bare filename of the draft (e.g., "001-commitment.md").

    Returns:
        JSON with filename, title, draft_id, and content.

    Raises:
        HTTPException 400: If the filename contains path traversal characters.
        HTTPException 404: If the file is not found.
    """
    # Reject any filename with directory separator characters
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(
            status_code=400,
            detail="Invalid filename: path traversal not allowed.",
        )

    content = read_draft_file(filename)
    if content is None:
        # Distinguish traversal from not-found by checking if the
        # file exists at all in the drafts dir
        drafts_dir = settings.drafts_dir
        candidate = drafts_dir / filename
        if not drafts_dir.exists() or not candidate.exists():
            raise HTTPException(status_code=404, detail=f"Draft '{filename}' not found.")
        raise HTTPException(
            status_code=400,
            detail="Invalid filename: path traversal not allowed.",
        )

    # Derive metadata from filename
    stem = Path(filename).stem
    parts = stem.split("-", 1)
    draft_id = parts[0] if parts[0].isdigit() else None
    title = parts[1].replace("-", " ").title() if len(parts) > 1 else stem

    return {
        "filename": filename,
        "draft_id": draft_id,
        "title": title,
        "content": content,
    }


# ---------------------------------------------------------------------------
# Publish endpoint (CSRF protected)
# ---------------------------------------------------------------------------

# Server-side dedup cache: content_hash -> timestamp
# Entries expire after 60 seconds. Max 100 entries.
_publish_dedup_cache: OrderedDict[str, float] = OrderedDict()
_DEDUP_WINDOW_SECONDS = 60
_PUBLISH_NONCE_COOKIE = "publish_nonce"


def _check_dedup(content_hash: str) -> bool:
    """Check if this content was published in the last 60 seconds.

    Returns True if duplicate detected (should reject).
    Purges expired entries on each call.
    """
    now = time.time()
    while _publish_dedup_cache:
        oldest_key, oldest_time = next(iter(_publish_dedup_cache.items()))
        if now - oldest_time > _DEDUP_WINDOW_SECONDS:
            _publish_dedup_cache.pop(oldest_key)
        else:
            break
    if content_hash in _publish_dedup_cache:
        return True
    # Evict oldest entry if at capacity
    if len(_publish_dedup_cache) >= 100:
        _publish_dedup_cache.popitem(last=False)
    _publish_dedup_cache[content_hash] = now
    return False


def generate_publish_nonce_cookie(response: Any) -> str:
    """Generate a publish nonce, set it as a cookie, and return the value.

    Called by the compose route to set up CSRF protection for the publish
    form before rendering the page.
    """
    import secrets
    nonce = secrets.token_urlsafe(32)
    response.set_cookie(
        key=_PUBLISH_NONCE_COOKIE,
        value=nonce,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return nonce


@router.post("/api/posts/publish")
async def publish_post(
    request: Request,
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """Publish a text post to LinkedIn and store locally.

    Request body (JSON):
        text: str           - Post body text (required, max 3000 chars)
        title: str | None   - Optional title for dashboard display
        draft_id: str | None - Optional draft ID to link
        post_id: int | None  - Optional existing post ID to update
        visibility: str     - "PUBLIC" (default) or "CONNECTIONS"
        save_as_draft: bool - If true, save locally without publishing
        csrf_token: str     - CSRF token (required for publish)

    Returns:
        JSON with post ID, LinkedIn URL (if published), and status.

    Raises:
        HTTPException 400: If text is empty or exceeds 3000 chars.
        HTTPException 401: If not connected to LinkedIn.
        HTTPException 403: If CSRF validation fails or w_member_social scope missing.
        HTTPException 409: If duplicate publish detected.
        HTTPException 429: If LinkedIn rate limited.
        HTTPException 502: If LinkedIn API call fails.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON request body.")

    text: str = body.get("text", "").strip()
    title: str | None = body.get("title") or None
    draft_id: str | None = body.get("draft_id") or None
    post_id: int | None = body.get("post_id") or None
    visibility: str = body.get("visibility", "PUBLIC")
    save_as_draft: bool = bool(body.get("save_as_draft", False))
    csrf_token: str | None = body.get("csrf_token") or None

    # Validate text
    if not text:
        raise HTTPException(status_code=400, detail="Post text cannot be empty.")
    if len(text) > 3000:
        raise HTTPException(
            status_code=400,
            detail=f"Post text exceeds 3000 characters ({len(text)}).",
        )

    # Validate visibility
    if visibility not in ("PUBLIC", "CONNECTIONS"):
        visibility = "PUBLIC"

    # --- Save as draft (no CSRF required, no LinkedIn API call) ---
    if save_as_draft:
        auto_title = title or text[:100]
        if post_id:
            existing = db.query(Post).filter(Post.id == post_id).first()
            if not existing:
                raise HTTPException(status_code=404, detail=f"Post {post_id} not found.")
            existing.content = text
            existing.title = auto_title
            if draft_id is not None:
                existing.draft_id = draft_id
            if not existing.status or existing.status == "draft":
                existing.status = "draft"
            existing.recalculate_engagement_rate()
            db.commit()
            db.refresh(existing)
            return {
                "id": existing.id,
                "status": existing.status,
                "title": existing.title,
                "linkedin_url": existing.post_url,
            }
        else:
            from datetime import date as _date
            post = Post(
                post_date=_date.today(),
                title=auto_title,
                content=text,
                status="draft",
                draft_id=draft_id,
            )
            post.recalculate_engagement_rate()
            db.add(post)
            db.commit()
            db.refresh(post)
            return {
                "id": post.id,
                "status": post.status,
                "title": post.title,
                "linkedin_url": None,
            }

    # --- Full publish flow ---

    # CSRF validation (nonce cookie + HMAC, same pattern as disconnect)
    from app.oauth import generate_disconnect_csrf_token, verify_disconnect_csrf_token
    nonce = request.cookies.get(_PUBLISH_NONCE_COOKIE)
    if not csrf_token or not nonce:
        raise HTTPException(
            status_code=403,
            detail="Missing CSRF token. Please reload the compose page and try again.",
        )
    # Reuse the same HMAC helper with a different prefix to avoid token reuse
    from app.config import settings as _settings
    import hmac as _hmac
    import hashlib as _hashlib
    key = _settings.token_encryption_key.encode()
    message = f"publish:{nonce}".encode()
    expected = _hmac.new(key, message, _hashlib.sha256).hexdigest()
    if not _hmac.compare_digest(expected, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token.")

    # Check OAuth connection
    from app.models import OAuthToken
    token_row = db.query(OAuthToken).filter(OAuthToken.provider == "linkedin").first()
    if not token_row:
        raise HTTPException(status_code=401, detail="Not connected to LinkedIn. Connect in Settings.")

    # Pre-flight scope check
    stored_scopes = token_row.scopes.split() if token_row.scopes else []
    if "w_member_social" not in stored_scopes:
        raise HTTPException(
            status_code=403,
            detail=(
                "Your LinkedIn connection needs to be updated. "
                "Please reconnect in Settings to enable publishing."
            ),
        )

    # Check member ID
    if not token_row.linkedin_member_id:
        raise HTTPException(
            status_code=403,
            detail=(
                "LinkedIn member ID not available. "
                "Please reconnect in Settings to refresh your connection."
            ),
        )

    # Idempotency check (60-second window)
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    if _check_dedup(content_hash):
        raise HTTPException(
            status_code=409,
            detail="Duplicate publish detected. Please wait 60 seconds before publishing the same content.",
        )

    # Get valid access token
    from app.oauth import get_valid_access_token
    access_token = get_valid_access_token(db)
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="LinkedIn access token is expired or unavailable. Please reconnect in Settings.",
        )

    # Build member URN
    member_urn = f"urn:li:person:{token_row.linkedin_member_id}"

    # Publish to LinkedIn
    from app.linkedin_client import LinkedInAPIError, LinkedInRateLimitError, create_post
    try:
        result = await create_post(access_token, member_urn, text, visibility)
    except LinkedInRateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail={
                "message": str(e),
                "retry_after_seconds": e.retry_after_seconds,
            },
        )
    except LinkedInAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Store the post in the database
    from datetime import date as _date
    auto_title = title or text[:100]

    if post_id:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail=f"Post {post_id} not found.")
        post.linkedin_post_id = result.activity_id
        post.post_url = result.post_url
        post.content = text
        post.status = "published"
        post.title = auto_title
        if draft_id is not None:
            post.draft_id = draft_id
        post.post_date = _date.today()
        post.recalculate_engagement_rate()
    else:
        post = Post(
            post_date=_date.today(),
            title=auto_title,
            linkedin_post_id=result.activity_id,
            post_url=result.post_url,
            content=text,
            status="published",
            draft_id=draft_id,
        )
        post.recalculate_engagement_rate()
        db.add(post)

    db.commit()
    db.refresh(post)

    logger.info(
        "Post published: id=%d linkedin_post_id=%s url=%s",
        post.id,
        result.activity_id,
        result.post_url,
    )

    return {
        "id": post.id,
        "status": post.status,
        "title": post.title,
        "linkedin_post_id": result.activity_id,
        "linkedin_url": result.post_url,
        "post_urn": result.post_urn,
    }


# ---------------------------------------------------------------------------
# Batch upload endpoint (per-post XLSX files)
# ---------------------------------------------------------------------------


@router.post("/api/upload/batch")
async def batch_upload(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """Upload multiple per-post XLSX files at once.

    Each file is processed independently using per-post XLSX ingestion.
    Partial failures do not block other files.

    Args:
        files: List of uploaded XLSX files.

    Returns:
        JSON with per-file results (successes and failures).
    """
    import shutil
    import tempfile

    from app.ingest import (
        DuplicateFileError,
        IngestError,
        compute_file_hash,
        validate_upload,
    )

    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    results: list[dict[str, Any]] = []

    for upload_file in files:
        filename = upload_file.filename or "unknown.xlsx"
        tmp_path = None
        try:
            # Save to a temporary file
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                shutil.copyfileobj(upload_file.file, tmp)
                tmp_path = Path(tmp.name)

            validate_upload(tmp_path)

            import openpyxl
            try:
                wb = openpyxl.load_workbook(tmp_path, read_only=False, data_only=True)
            except Exception as exc:
                raise IngestError(f"Cannot open workbook: {exc}") from exc

            from app.ingest import _detect_xlsx_format, ingest_per_post_xlsx
            fmt = _detect_xlsx_format(wb)

            if fmt == "per_post":
                file_hash = compute_file_hash(tmp_path)
                existing_upload = db.query(Upload).filter_by(file_hash=file_hash).first()
                if existing_upload:
                    wb.close()
                    results.append({
                        "filename": filename,
                        "status": "duplicate",
                        "message": f"Already imported on {existing_upload.upload_date}.",
                    })
                    continue

                per_post_result = ingest_per_post_xlsx(db, wb)
                wb.close()

                upload_record = Upload(
                    filename=filename,
                    file_hash=file_hash,
                    records_imported=1,
                    status="completed",
                )
                db.add(upload_record)
                db.commit()

                results.append({
                    "filename": filename,
                    "status": "ok",
                    "post_id": per_post_result["post_id"],
                    "demographics_imported": per_post_result["demographics_imported"],
                })
            elif fmt == "aggregate":
                wb.close()
                results.append({
                    "filename": filename,
                    "status": "error",
                    "message": "This file looks like an aggregate export. Use the main upload endpoint.",
                })
            else:
                wb.close()
                results.append({
                    "filename": filename,
                    "status": "error",
                    "message": "Unrecognised XLSX format (expected PERFORMANCE + TOP DEMOGRAPHICS sheets).",
                })

        except IngestError as exc:
            results.append({
                "filename": filename,
                "status": "error",
                "message": str(exc),
            })
        except Exception as exc:
            logger.exception("Unexpected error processing %s", filename)
            results.append({
                "filename": filename,
                "status": "error",
                "message": "Unexpected error during processing.",
            })
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    successes = sum(1 for r in results if r["status"] == "ok")
    return {
        "total": len(results),
        "succeeded": successes,
        "failed": len(results) - successes,
        "results": results,
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
