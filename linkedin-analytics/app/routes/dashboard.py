"""Dashboard page routes: main view, post detail, audience, settings."""

import logging
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_session
from app.models import DailyMetric, DemographicSnapshot, FollowerSnapshot, Post, PostDemographic, Upload

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

    # Per-post demographics (from per-post XLSX imports)
    post_demographics = (
        db.query(PostDemographic)
        .filter(PostDemographic.post_id == post_id)
        .order_by(PostDemographic.category, PostDemographic.percentage.desc())
        .all()
    )
    # Group demographics by category for the template
    demo_by_category: dict[str, list] = {}
    for d in post_demographics:
        d_display = type("DemoDisplay", (), {
            "category": d.category,
            "value": d.value,
            "percentage": round(d.percentage * 100, 1),
        })()
        demo_by_category.setdefault(d.category, []).append(d_display)

    return templates.TemplateResponse(
        request,
        "post_detail.html",
        {
            "post": post,
            "daily_metrics": daily_metrics,
            "prev_post": prev_post,
            "next_post": next_post,
            "demo_by_category": demo_by_category,
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


@router.get("/dashboard/settings", response_class=HTMLResponse)
async def dashboard_settings(
    request: Request,
    response: Response,
    db: Session = Depends(get_session),
) -> HTMLResponse:
    """Render the settings page with OAuth connection status."""
    from app.oauth import get_auth_status
    from app.routes.oauth_routes import generate_nonce_cookie
    from datetime import datetime, timezone

    auth_status = None
    disconnect_csrf_token = None
    nonce = None

    if settings.oauth_enabled:
        auth_status = get_auth_status(db)
        nonce = generate_nonce_cookie(response)
        from app.oauth import generate_disconnect_csrf_token
        disconnect_csrf_token = generate_disconnect_csrf_token(nonce)

    # Compute relative expiry displays for the template.
    access_expires_days = None
    refresh_expires_days = None
    refresh_warning = False

    if auth_status and auth_status.connected:
        now = datetime.now(timezone.utc)
        if auth_status.expires_at:
            expires_at = auth_status.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            access_expires_days = (expires_at - now).days
        if auth_status.refresh_expires_at:
            refresh_expires_at = auth_status.refresh_expires_at
            if refresh_expires_at.tzinfo is None:
                refresh_expires_at = refresh_expires_at.replace(tzinfo=timezone.utc)
            refresh_expires_days = (refresh_expires_at - now).days
            refresh_warning = refresh_expires_days <= 30

    connected_param = request.query_params.get("connected")
    disconnected_param = request.query_params.get("disconnected")
    error_param = request.query_params.get("error")

    # Whitelist known error values to prevent reflected content injection.
    _KNOWN_ERRORS = {"user_cancelled_authorize", "token_exchange_failed"}
    flash_error = error_param if error_param in _KNOWN_ERRORS else ("unknown_error" if error_param else None)

    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "oauth_enabled": settings.oauth_enabled,
            "auth_status": auth_status,
            "disconnect_csrf_token": disconnect_csrf_token,
            "access_expires_days": access_expires_days,
            "refresh_expires_days": refresh_expires_days,
            "refresh_warning": refresh_warning,
            "flash_connected": connected_param == "1",
            "flash_disconnected": disconnected_param == "1",
            "flash_error": flash_error,
        },
    )


@router.get("/dashboard/compose", response_class=HTMLResponse)
async def compose(
    request: Request,
    response: Response,
    draft: str | None = None,
    post_id: int | None = None,
    db: Session = Depends(get_session),
) -> HTMLResponse:
    """Render the post composer page.

    If ?draft=filename is provided, the draft content is passed to the template
    for pre-loading (frontmatter stripped).
    If ?post_id=N is provided, pre-loads a saved draft post for editing.
    """
    from app.oauth import get_auth_status
    from app.routes.api import generate_publish_nonce_cookie, list_draft_files, read_draft_file
    import hashlib as _hashlib
    import hmac as _hmac

    auth_status = None
    if settings.oauth_enabled:
        auth_status = get_auth_status(db)

    has_publish_scope = (
        auth_status is not None
        and auth_status.connected
        and "w_member_social" in auth_status.scopes
    )

    # Generate CSRF nonce for publish action
    nonce = generate_publish_nonce_cookie(response)
    key = settings.token_encryption_key.encode() if settings.token_encryption_key else b""
    if key:
        message = f"publish:{nonce}".encode()
        publish_csrf_token = _hmac.new(key, message, _hashlib.sha256).hexdigest()
    else:
        publish_csrf_token = ""

    # Load draft content if requested
    prefill_content = None
    prefill_title = None
    prefill_draft_id = None

    if draft:
        prefill_content = read_draft_file(draft)
        stem = Path(draft).stem
        parts = stem.split("-", 1)
        prefill_draft_id = parts[0] if parts[0].isdigit() else None
        prefill_title = parts[1].replace("-", " ").title() if len(parts) > 1 else stem

    # Load existing draft post if post_id provided
    existing_post = None
    if post_id:
        existing_post = db.query(Post).filter(Post.id == post_id).first()
        if existing_post:
            prefill_content = prefill_content or existing_post.content or ""
            prefill_title = prefill_title or existing_post.title or ""
            prefill_draft_id = prefill_draft_id or existing_post.draft_id

    available_drafts = list_draft_files()

    return templates.TemplateResponse(
        request,
        "compose.html",
        {
            "oauth_enabled": settings.oauth_enabled,
            "auth_status": auth_status,
            "has_publish_scope": has_publish_scope,
            "publish_csrf_token": publish_csrf_token,
            "available_drafts": available_drafts,
            "prefill_content": prefill_content or "",
            "prefill_title": prefill_title or "",
            "prefill_draft_id": prefill_draft_id or "",
            "existing_post": existing_post,
        },
    )


@router.get("/dashboard/posts", response_class=HTMLResponse)
async def posts_browser(
    request: Request,
    status_filter: str | None = None,
    sort: str = "post_date",
    db: Session = Depends(get_session),
) -> HTMLResponse:
    """Render the posts browser with unified timeline."""
    from app.routes.api import list_draft_files

    # Validate sort parameter
    valid_sorts = {"post_date", "impressions", "engagement_rate"}
    if sort not in valid_sorts:
        sort = "post_date"

    sort_map = {
        "post_date": Post.post_date,
        "impressions": Post.impressions,
        "engagement_rate": Post.engagement_rate,
    }
    sort_col = sort_map[sort]

    query = db.query(Post)
    if status_filter == "draft":
        query = query.filter(Post.status == "draft")
    elif status_filter == "published":
        query = query.filter(Post.status == "published")
    elif status_filter == "linked":
        query = query.filter(Post.status == "analytics_linked")
    elif status_filter == "imported":
        query = query.filter(Post.status.is_(None))

    posts = query.order_by(desc(sort_col)).limit(200).all()

    # Get draft files not yet linked to any post
    all_drafts = list_draft_files()
    linked_draft_ids = {p.draft_id for p in db.query(Post.draft_id).all() if p.draft_id}
    unlinked_drafts = [
        d for d in all_drafts
        if d["draft_id"] not in linked_draft_ids
    ]

    total_posts = db.query(func.count(Post.id)).scalar() or 0

    return templates.TemplateResponse(
        request,
        "posts.html",
        {
            "posts": posts,
            "status_filter": status_filter,
            "sort": sort,
            "unlinked_drafts": unlinked_drafts,
            "total_posts": total_posts,
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
