# Technical Implementation Plan: Post Composer and Content Management

**Feature:** Post composition, publishing, draft management, content viewing, LinkedIn URN linking, and per-post XLSX analytics import
**Created:** 2026-03-01
**Revised:** 2026-03-01
**Author:** Architect

---

## Context Alignment

### CLAUDE.md Patterns Followed
- **Existing stack:** FastAPI + SQLAlchemy + SQLite + Jinja2 + Tailwind CDN + Chart.js + Pydantic Settings. No new frameworks introduced. No new dependencies required.
- **Config via Pydantic Settings:** No new env vars needed. The existing `linkedin_client_id`, `linkedin_client_secret`, `token_encryption_key`, and `linkedin_api_version` settings are sufficient.
- **Dark theme consistency:** New pages (Compose, Posts browser, Timeline) use the existing Navy #0a0f1a / card #111827 / accent #3b82f6 palette with Inter + JetBrains Mono fonts.
- **Sensitivity protocol:** Post content is stored locally and never shared externally. The composer only publishes to the user's own LinkedIn account. No employer-identifiable data is involved. Draft file paths reference local files only.
- **No em-dashes:** All copy in this plan, templates, and UI text avoids em-dashes.
- **Single-user, self-hosted:** One LinkedIn account, one set of drafts, one database. No multi-tenant concerns.
- **httpx for outbound calls:** The LinkedIn Posts API calls use `httpx.AsyncClient`, already in requirements.txt, consistent with the existing oauth.py pattern. All outbound API calls are async to avoid blocking the event loop.
- **Migration script pattern:** New columns on the existing `posts` table are added via an idempotent migration script, following the precedent set by `scripts/migrate_001_cohort_columns.py`.
- **Content pipeline integration:** The draft management feature connects `~/bksp/drafts/linkedin/` draft files to the dashboard, supporting the existing content pipeline (`/mine` -> `/pitch-review` -> write -> `/review` -> `/publish` -> `/repurpose`).

### Prior Plans Consulted
- `plans/linkedin-oauth-auth.md` (APPROVED): Established the OAuth flow, token encryption, `get_valid_access_token()`, and the `OAuthToken` model. This plan depends on that infrastructure for API authentication. The `_SCOPES` constant needs to be updated to include `w_member_social`.
- `plans/engagement-analytics.md` (APPROVED): Established the pattern for adding cohort columns via migration scripts, new API endpoints, and new templates. This plan follows the same patterns.
- `plans/linkedin-analytics-dashboard.md` (APPROVED): Established the full architecture. Phase 3 mentions API integration. This plan implements the post publishing component of Phase 3 using `w_member_social` (which does not require Community Management API approval).
- `plans/bksp-social-cma-app.md` (NOT APPROVED, ABANDONED): Attempted standalone CMA app, blocked by business registration. This plan avoids any CMA-dependent features.
- `.claude/agents/linkedin-api-architect.md`: Defines design principles for API integration: token encryption, separation of concerns, graceful degradation, rate limiting, API versioning. This plan follows all of these.

### Review Findings Incorporated

This revision addresses findings from three review documents:

**Red team review** (`dashboard-post-composer.redteam.md`, verdict: FAIL):
- Finding 1 (Critical): URN mismatch. **RESOLVED** by per-post XLSX export discovery (see Section 10).
- Finding 2 (Major): CSRF on publish. **ADDRESSED** in Section 6.
- Finding 3 (Major): Path traversal. **FIXED** with `Path.is_relative_to()`.
- Finding 4 (Major): Member ID race condition. **FIXED** by restructuring callback.
- Finding 5 (Major): Synchronous httpx. **FIXED** with `httpx.AsyncClient`.
- Finding 6 (Major): No idempotency on publish. **ADDRESSED** with client+server dedup.
- Finding 7 (Minor): Frontmatter not stripped. **FIXED** in draft reader.
- Finding 8 (Minor): Orphan draft rows. Accepted as-is; single-user app, low risk.
- Finding 9 (Minor): No rate limit backoff. **ADDRESSED** with 429 handling.
- Finding 10 (Minor): `content_format` naming. Accepted; renaming would break existing API consumers.
- Finding 11 (Minor): Character limit validation. Accepted; surface API error if mismatch.
- Finding 12 (Info): Migration default status. **ADDRESSED** with `IS NULL` query pattern.
- Finding 13 (Info): Token expiry during publish. Accepted; 5-minute buffer is sufficient.
- Finding 14 (Info): No scope visibility check. **ADDRESSED** with pre-flight scope check.
- Finding 15 (Info): No rollback strategy. **ADDRESSED** with backup step in rollout.

**Librarian review** (`dashboard-post-composer.review.md`, verdict: PASS):
- No required edits. Optional suggestions noted and incorporated where applicable.

**Feasibility review** (`dashboard-post-composer.feasibility.md`, verdict: PASS):
- C1 (Critical): URN mismatch. **RESOLVED** by per-post XLSX export discovery.
- C2 (Critical): `/rest/posts` vs `/v2/ugcPosts`. **ADDRESSED** with Phase 0 verification step.
- M1 (Major): Path traversal. **FIXED**.
- M2 (Major): CSRF. **ADDRESSED**.
- M3 (Major): Rate limits. **ADDRESSED**.
- M4 (Major): Scope check. **ADDRESSED**.
- M5 (Major): Draft-to-publish duplicates. **ADDRESSED** with `post_id` parameter on publish.

### Deviations from Established Patterns
- **OAuth scope expansion:** The current `_SCOPES` constant in `oauth.py` is `"openid profile"`. This plan requires adding `w_member_social` to the scope string. Users who already connected their LinkedIn account will need to re-authorize to grant the new scope. Justification: `w_member_social` is auto-granted with "Share on LinkedIn" product (already configured). Re-authorization is a one-time action, and the settings page already handles the reconnection flow.
- **New `linkedin_client.py` module:** The project currently has no outbound API calls to LinkedIn beyond OAuth token exchange. This plan introduces a new module for LinkedIn API interactions, keeping it separate from `oauth.py` (which handles only authentication). This follows the linkedin-api-architect's "separation of concerns" principle.
- **Draft file reading:** The app reads markdown files from `~/bksp/drafts/linkedin/` at runtime. This introduces a filesystem dependency outside the app's `data_dir`. The path is configurable via a new `DRAFTS_DIR` setting with a sensible default. Docker deployments must mount this path as a volume.
- **Per-post XLSX import:** A second XLSX import parser handles key-value format files (per-post exports from LinkedIn), distinct from the existing tabular aggregate export parser. Format auto-detection by sheet names keeps a single upload endpoint.

---

## Goals

1. Build a Post Composer page that creates and publishes LinkedIn posts directly from the dashboard using the `w_member_social` scope and the LinkedIn REST Posts API
2. Automatically capture and store the LinkedIn post URN (`x-restli-id` response header) after publishing, pre-linking the post to future XLSX analytics imports
3. Store post content (body text) locally in the database so posts are viewable alongside their analytics
4. Integrate with existing LinkedIn draft files at `~/bksp/drafts/linkedin/` so drafts can be browsed, loaded into the composer, and published directly
5. Build a Posts browser page with a unified timeline showing drafts, published posts, and their analytics linkage status
6. Enhance XLSX import matching to automatically link imported analytics to posts previously published via the API (by URN exact match)
7. Import per-post XLSX exports to capture additional metrics (saves, sends, profile views, followers gained, reposts) and per-post demographics

## Non-Goals

- **Analytics API calls:** No post analytics data retrieval via API. Analytics data still comes from manual XLSX exports only.
- **Image/video/document uploads:** The composer supports text-only posts in v1. Image, video, and document posting requires the LinkedIn Images/Videos/Documents APIs with asset upload workflows, which adds significant complexity. Can be added later.
- **Post scheduling:** No deferred publishing. Posts are published immediately when the user clicks "Publish." Scheduling requires a background task runner, which the app does not currently have.
- **Post editing on LinkedIn:** The LinkedIn Posts API supports partial updates to `commentary`, but editing published posts is a risky operation (changes what followers already saw). Out of scope.
- **Post deletion on LinkedIn:** Supported by the API but excluded from v1 to avoid accidental data loss.
- **Markdown rendering in LinkedIn:** LinkedIn does not support markdown. The composer works with plain text. Unicode formatting (bold, italic via Unicode characters) is a nice-to-have for a future iteration.
- **Article link preview:** LinkedIn's Posts API does not support URL scraping for article posts. Article posts with thumbnails require the Images API. Out of scope for v1.
- **Bulk publish:** Publishing multiple drafts in one action. Too risky for v1; publish one at a time.

## Assumptions

1. The user has already completed the LinkedIn OAuth setup (per `plans/linkedin-oauth-auth.md`) and has a connected LinkedIn account.
2. The LinkedIn developer app has "Share on LinkedIn" product enabled (auto-granted), which provides the `w_member_social` scope.
3. The `w_member_social` scope is sufficient for creating posts on behalf of the authenticated member. This is confirmed by LinkedIn's Posts API documentation. Phase 0 includes a verification step to confirm which endpoint (`/rest/posts` vs `/v2/ugcPosts`) works with the app's current product access.
4. The LinkedIn member ID (person URN sub) is fetched during the OAuth callback and stored in `OAuthToken.linkedin_member_id`. This plan restructures the callback to fetch the member ID before storing tokens (resolves the race condition identified in the red team review).
5. Draft files at `~/bksp/drafts/linkedin/` follow the naming convention `NNN-slug.md` (e.g., `001-commitment-without-execution.md`). Files ending in `.copy-review.md`, `.sensitivity-review.md`, `.review-summary.md`, or `.visual-specs.md` are supplementary review files and are excluded from the draft list.
6. LinkedIn's Posts API returns a `201` response with the post URN in the `x-restli-id` response header. This is the canonical method for obtaining the post ID after creation.
7. The app runs in a single-process mode (uvicorn with one worker). No distributed locking is needed for API calls.
8. Per-post XLSX exports are named `PostAnalytics_*.xlsx` and contain sheets named "PERFORMANCE" and "TOP DEMOGRAPHICS". Aggregate exports contain sheets named "DISCOVERY" and "ENGAGEMENT". This naming difference enables auto-detection of export format.
9. The per-post XLSX "Post URL" field contains `urn:li:share:{id}`, which is the same URN format returned by the Posts API. This resolves the URN mismatch concern from the red team and feasibility reviews (see Section 10).

---

## Proposed Design

### Architecture Overview

```
User writes/loads content in Post Composer
    |
    v
POST /api/posts/publish
    |-- Validate CSRF token (nonce cookie + HMAC, same pattern as disconnect)
    |-- Validate content (non-empty, <= 3000 chars)
    |-- Check w_member_social in stored scopes (pre-flight)
    |-- Check idempotency (content hash dedup, 60-second window)
    |-- Get valid access token via get_valid_access_token()
    |-- Get member URN from OAuthToken.linkedin_member_id
    |-- POST https://api.linkedin.com/rest/posts (async httpx)
    |   Headers: Authorization, LinkedIn-Version, X-Restli-Protocol-Version, Content-Type
    |   Body: { author, commentary, visibility, distribution, lifecycleState }
    |   On 429: parse Retry-After header, return user-friendly message
    |-- Extract post URN from x-restli-id response header
    |-- Create/update Post row in DB:
    |   - linkedin_post_id = extracted share ID from URN
    |   - post_url = constructed LinkedIn post URL
    |   - content = full post text
    |   - status = "published"
    |   - post_date = today
    |-- Return post ID and LinkedIn URL to UI
    |
    v
Per-Post XLSX Import (NEW)
    |-- Auto-detect format by sheet names:
    |   - PERFORMANCE + TOP DEMOGRAPHICS = per-post export
    |   - DISCOVERY + ENGAGEMENT = aggregate export (existing)
    |-- Parse key-value pairs from PERFORMANCE sheet
    |-- Extract linkedin_post_id from Post URL (urn:li:share:{id})
    |-- Extract post_hour from Post Publish Time
    |-- Store saves, sends, profile_views, followers_gained, reposts
    |-- Parse TOP DEMOGRAPHICS sheet for per-post demographics
    |-- Upsert PostDemographic rows with post_id FK
    |
    v
XLSX Import (existing flow, enhanced matching)
    |-- For each imported post with a linkedin_post_id:
    |   - Try exact match on linkedin_post_id (existing behavior)
    |   - If match found, merge analytics into existing Post row
    |   - Post now has both content (from composer) and analytics (from XLSX)
    |
    v
Posts Browser / Timeline
    |-- Shows all posts with status indicators:
    |   - "draft" (local draft file, not published)
    |   - "published" (published via API, no analytics yet)
    |   - "linked" (published with analytics from XLSX import)
    |-- Content is viewable inline for posts created via composer
```

### Module Structure

```
linkedin-analytics/app/
  linkedin_client.py        # NEW: LinkedIn API client (create post, get member info)
  oauth.py                  # MODIFIED: Update _SCOPES, add member ID fetch on callback
  models.py                 # MODIFIED: Add content, status, new metric columns to Post; add PostDemographic model
  config.py                 # MODIFIED: Add DRAFTS_DIR setting
  ingest.py                 # MODIFIED: Add per-post XLSX parser, enhance _upsert_post
  routes/
    api.py                  # MODIFIED: Add POST /api/posts/publish, GET /api/drafts
    dashboard.py            # MODIFIED: Add /dashboard/compose, /dashboard/posts routes
  templates/
    compose.html            # NEW: Post composer page
    posts.html              # NEW: Posts browser / timeline page
    post_detail.html        # MODIFIED: Show post content, status indicator, per-post demographics, new metrics
    base.html               # MODIFIED: Add "Compose" and "Posts" nav items
scripts/
  migrate_002_post_content.py  # NEW: Add content, status, new metric columns; create post_demographics table
tests/
  test_linkedin_client.py   # NEW: Tests for LinkedIn API client
  test_compose.py           # NEW: Tests for compose routes and publish flow
  test_per_post_ingest.py   # NEW: Tests for per-post XLSX import
```

### 1. Schema Changes (`app/models.py`)

Add new columns to the `Post` model and a new `PostDemographic` model:

```python
class Post(Base):
    # ... existing columns ...

    # NEW: Post body content (stored locally when composed in dashboard)
    content: str | None = Column("content", Text, nullable=True)

    # NEW: Post lifecycle status
    # Values: "draft", "published", "analytics_linked"
    # - "draft": composed in dashboard but not yet published to LinkedIn
    # - "published": published to LinkedIn via API (has linkedin_post_id)
    # - "analytics_linked": published and has analytics data from XLSX import
    # - None: imported from XLSX only (no local content, legacy behavior)
    status: str | None = Column("status", String(20), nullable=True)

    # NEW: Additional per-post metrics from per-post XLSX export
    saves: int | None = Column(Integer, nullable=True, default=0)
    sends: int | None = Column(Integer, nullable=True, default=0)
    profile_views: int | None = Column(Integer, nullable=True, default=0)
    followers_gained: int | None = Column(Integer, nullable=True, default=0)
    reposts: int | None = Column(Integer, nullable=True, default=0)

    # Relationship to per-post demographics
    demographics = relationship(
        "PostDemographic", back_populates="post", cascade="all, delete-orphan"
    )
```

New `PostDemographic` model for per-post demographics from per-post XLSX exports:

```python
class PostDemographic(Base):
    """Per-post demographic breakdown from LinkedIn per-post XLSX export.

    Stores category/value/percentage triples for each post. Categories include:
    - "company_size": e.g., "10,001+ employees", "1001-5000 employees"
    - "job_title": e.g., "Software Engineer", "Security Engineer"
    - "location": e.g., "Fredericton", "Greater Toronto Area, Canada"
    - "company": e.g., "IBM", "OCAS"

    The "company_size" and "company" categories are new (only available in
    per-post exports, not in the aggregate DISCOVERY/ENGAGEMENT export).
    """
    __tablename__ = "post_demographics"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    post_id: int = Column(Integer, ForeignKey("posts.id"), nullable=False)
    category: str = Column(String, nullable=False)
    value: str = Column(String, nullable=False)
    percentage: float = Column(Float, nullable=False)
    created_at: datetime = Column(DateTime, default=func.now())

    post = relationship("Post", back_populates="demographics")

    __table_args__ = (
        UniqueConstraint(
            "post_id", "category", "value", name="uq_post_demo"
        ),
    )

    def __repr__(self) -> str:
        return f"<PostDemographic post={self.post_id} {self.category}={self.value}>"
```

The `status` column is nullable to preserve backward compatibility with existing XLSX-imported posts that have no status. The display logic treats `None` as "imported" (analytics-only, no local content). Queries filtering for imported posts use `status IS NULL`, not `status = 'imported'`.

Add a `content` property to `_serialize_post` in `api.py` and update `display_title` to prefer content-derived titles.

### 2. Configuration (`app/config.py`)

Add one new setting:

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Path to LinkedIn draft files (markdown). Default assumes bksp project structure.
    # MUST be explicitly set in Docker environments (Path.home() may not resolve correctly).
    drafts_dir: Path = Path.home() / "bksp" / "drafts" / "linkedin"
```

In Docker, this path is mounted as a volume: `-v ~/bksp/drafts/linkedin:/app/drafts/linkedin`. The `DRAFTS_DIR` env var must be set to `/app/drafts/linkedin` in Docker. Update `docker-compose.yml` to include the volume mount.

### 3. LinkedIn API Client (`app/linkedin_client.py`)

New module responsible for all LinkedIn REST API interactions beyond OAuth. Uses `httpx.AsyncClient` for all outbound calls to avoid blocking the async event loop.

```python
"""LinkedIn REST API client for post creation.

Uses the Posts API (https://api.linkedin.com/rest/posts) with the
w_member_social scope. All API calls require the LinkedIn-Version and
X-Restli-Protocol-Version headers.

Follows the linkedin-api-architect design principles:
- Token values never logged
- Exception messages sanitized
- Rate limit headers logged
- API version pinned in config

IMPORTANT: All functions in this module are async. They use httpx.AsyncClient
to avoid blocking the FastAPI event loop.
"""

import logging
import re
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Endpoint configuration.
# The primary endpoint is /rest/posts (REST API). If the app only has
# "Share on LinkedIn" product access and /rest/posts returns 403,
# fall back to /v2/ugcPosts (legacy endpoint, different payload format).
# Phase 0 testing determines which endpoint to use.
_POSTS_URL = "https://api.linkedin.com/rest/posts"
_UGCPOSTS_URL = "https://api.linkedin.com/v2/ugcPosts"
_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

# LinkedIn post character limit
MAX_POST_LENGTH = 3000


class LinkedInAPIError(Exception):
    """Raised when a LinkedIn API call fails. Message is sanitized."""


class LinkedInRateLimitError(LinkedInAPIError):
    """Raised when LinkedIn returns 429. Includes retry_after_seconds."""
    def __init__(self, message: str, retry_after_seconds: int | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


@dataclass
class PublishResult:
    """Result from publishing a post to LinkedIn."""
    post_urn: str           # Full URN (e.g., "urn:li:share:123456")
    activity_id: str        # Extracted numeric ID
    post_url: str           # Constructed LinkedIn post URL


def _build_headers(access_token: str) -> dict[str, str]:
    """Build the required headers for LinkedIn REST API calls."""
    return {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": settings.linkedin_api_version,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


def _log_rate_limits(response: httpx.Response) -> None:
    """Log LinkedIn rate limit headers if present."""
    limit = response.headers.get("X-RateLimit-Limit")
    remaining = response.headers.get("X-RateLimit-Remaining")
    if limit or remaining:
        logger.info("LinkedIn rate limits: %s/%s remaining", remaining, limit)


def _extract_activity_id(urn: str) -> str | None:
    """Extract the numeric activity/share ID from a LinkedIn URN.

    Handles all three formats:
    - urn:li:share:6844785523593134080
    - urn:li:ugcPost:68447855235931240
    - urn:li:activity:6844785523593134080
    """
    match = re.search(r"urn:li:(?:share|ugcPost|activity):(\d+)", urn)
    return match.group(1) if match else None


async def create_post(
    access_token: str,
    member_urn: str,
    text: str,
    visibility: str = "PUBLIC",
) -> PublishResult:
    """Publish a text-only post to LinkedIn.

    Args:
        access_token: Valid OAuth access token.
        member_urn: Author URN (e.g., "urn:li:person:abc123").
        text: Post body text (max 3000 characters).
        visibility: Post visibility ("PUBLIC" or "CONNECTIONS").

    Returns:
        PublishResult with the post URN, activity ID, and URL.

    Raises:
        LinkedInAPIError: On any API error (sanitized message).
        LinkedInRateLimitError: On 429 with retry_after_seconds if available.
        ValueError: If text is empty or exceeds MAX_POST_LENGTH.
    """
    if not text or not text.strip():
        raise ValueError("Post text cannot be empty.")
    if len(text) > MAX_POST_LENGTH:
        raise ValueError(
            f"Post text exceeds {MAX_POST_LENGTH} characters ({len(text)})."
        )

    payload = {
        "author": member_urn,
        "commentary": text,
        "visibility": visibility,
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    headers = _build_headers(access_token)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                _POSTS_URL,
                json=payload,
                headers=headers,
                timeout=httpx.Timeout(15.0),
            )
        _log_rate_limits(response)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        logger.error(
            "LinkedIn Posts API returned status %d", status
        )
        if status == 429:
            retry_after = e.response.headers.get("Retry-After")
            retry_seconds = int(retry_after) if retry_after and retry_after.isdigit() else None
            raise LinkedInRateLimitError(
                f"Rate limited by LinkedIn. Try again in {retry_seconds or 'a few'} seconds.",
                retry_after_seconds=retry_seconds,
            ) from None
        raise LinkedInAPIError(
            f"LinkedIn returned status {status}"
        ) from None
    except httpx.HTTPError:
        logger.error("LinkedIn Posts API call failed: network error")
        raise LinkedInAPIError(
            "Network error while publishing to LinkedIn"
        ) from None

    # Extract post URN from x-restli-id header
    post_urn = response.headers.get("x-restli-id", "")
    if not post_urn:
        logger.error("LinkedIn did not return x-restli-id header")
        raise LinkedInAPIError(
            "Post was created but LinkedIn did not return a post ID"
        )

    activity_id = _extract_activity_id(post_urn)
    if not activity_id:
        logger.warning(
            "Could not extract activity ID from URN: %s", post_urn
        )
        activity_id = post_urn  # Fallback: store the full URN

    # Construct the LinkedIn post URL
    post_url = f"https://www.linkedin.com/feed/update/{post_urn}/"

    logger.info("Published post: %s", post_url)

    return PublishResult(
        post_urn=post_urn,
        activity_id=activity_id,
        post_url=post_url,
    )


async def get_member_id(access_token: str) -> str | None:
    """Fetch the authenticated member's LinkedIn ID from /v2/userinfo.

    Returns the 'sub' claim from the userinfo response, which is the
    person identifier used to construct the author URN
    (urn:li:person:{sub}).

    Returns None if the call fails (non-fatal; the member ID is cached
    in OAuthToken.linkedin_member_id after the first successful fetch).
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                _USERINFO_URL,
                headers=headers,
                timeout=httpx.Timeout(10.0),
            )
        response.raise_for_status()
        data = response.json()
        return data.get("sub")
    except (httpx.HTTPError, KeyError, ValueError) as e:
        logger.warning("Failed to fetch member ID from /userinfo: %s", type(e).__name__)
        return None
```

**Endpoint verification note:** The `/rest/posts` endpoint is part of the Marketing/Community Management API surface. The "Share on LinkedIn" product grants `w_member_social` which may only work with the legacy `/v2/ugcPosts` endpoint. Phase 0 includes a manual test to determine which endpoint works. If `/rest/posts` returns 403, the implementation switches to `/v2/ugcPosts` with the following payload differences:

| Field | `/rest/posts` | `/v2/ugcPosts` |
|---|---|---|
| Text content | `commentary` | `specificContent.com.linkedin.ugc.ShareContent.shareCommentary.text` |
| Visibility | `visibility` (string) | `visibility.com.linkedin.ugc.MemberNetworkVisibility` (string) |
| Distribution | `distribution` (object) | Not required |
| Lifecycle | `lifecycleState` (string) | `lifecycleState` (string, same) |
| Author | `author` (string) | `author` (string, same) |

The `linkedin_client.py` module should be implemented to support both endpoints, with a config flag to switch between them. The response format is the same (201 + `x-restli-id` header).

### 4. OAuth Scope Update (`app/oauth.py`)

Update the `_SCOPES` constant:

```python
# Before:
_SCOPES = "openid profile"

# After:
_SCOPES = "openid profile w_member_social"
```

Restructure the OAuth callback to fetch the member ID BEFORE storing tokens (resolves the race condition from red team finding #4):

```python
# In oauth_routes.py, restructured callback flow:
from app.linkedin_client import get_member_id

# 1. Exchange authorization code for tokens
token_response = await exchange_code(code)

# 2. Immediately fetch member ID using the new access token
member_id = await get_member_id(token_response["access_token"])

# 3. Store tokens AND member_id together in a single call
store_tokens(db, token_response, member_id=member_id)
```

This eliminates the window where a token row exists without a `linkedin_member_id`.

### 5. Draft File Reader

Drafts are read from the filesystem at request time (not imported into DB). This keeps them editable via any text editor and in sync with the content pipeline.

```python
# In api.py or a new drafts module
import re as _re

def list_draft_files() -> list[dict]:
    """List LinkedIn draft files from the configured drafts directory.

    Returns a list of dicts with keys: draft_id, filename, path, title.
    Filters out review/supplementary files (*.copy-review.md, etc.).
    """
    drafts_dir = settings.drafts_dir
    if not drafts_dir.exists():
        return []

    # Exclude supplementary review files
    exclude_suffixes = {
        ".copy-review.md",
        ".sensitivity-review.md",
        ".review-summary.md",
        ".visual-specs.md",
    }

    drafts = []
    for f in sorted(drafts_dir.glob("*.md")):
        if any(f.name.endswith(suffix) for suffix in exclude_suffixes):
            continue

        # Extract draft_id from filename (e.g., "001" from "001-commitment-without-execution.md")
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


def read_draft_file(filename: str) -> str | None:
    """Read a draft file's content with frontmatter stripped.

    Returns None if not found or if path traversal is detected.
    Only reads files from the configured drafts directory.
    """
    drafts_dir = settings.drafts_dir
    # Security: resolve the path and verify it is within drafts_dir
    target = (drafts_dir / filename).resolve()
    if not target.is_relative_to(drafts_dir.resolve()):
        return None
    if not target.exists():
        return None
    raw = target.read_text(encoding="utf-8")
    return _strip_frontmatter(raw)
```

### 6. API Endpoints

#### POST /api/posts/publish

Publishes a post to LinkedIn and stores the content + URN locally. Includes CSRF protection (nonce cookie + HMAC token, same pattern as the disconnect endpoint in `oauth_routes.py`), pre-flight scope check, and idempotency protection.

```python
import hashlib
import time
from collections import OrderedDict

# Server-side dedup cache: content_hash -> timestamp
# Entries expire after 60 seconds. Max 100 entries.
_publish_dedup_cache: OrderedDict[str, float] = OrderedDict()
_DEDUP_WINDOW_SECONDS = 60


def _check_dedup(content_hash: str) -> bool:
    """Check if this content was published in the last 60 seconds.

    Returns True if duplicate detected (should reject).
    """
    now = time.time()
    # Purge expired entries
    while _publish_dedup_cache:
        oldest_key, oldest_time = next(iter(_publish_dedup_cache.items()))
        if now - oldest_time > _DEDUP_WINDOW_SECONDS:
            _publish_dedup_cache.pop(oldest_key)
        else:
            break
    if content_hash in _publish_dedup_cache:
        return True
    _publish_dedup_cache[content_hash] = now
    return False


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
        post_id: int | None  - Optional existing draft post ID to update (instead of creating new)
        visibility: str     - "PUBLIC" (default) or "CONNECTIONS"
        save_as_draft: bool - If true, save locally without publishing
        csrf_token: str     - CSRF token (required for publish, not for save_as_draft)

    Returns:
        JSON with post ID, LinkedIn URL, and status.

    Raises:
        HTTPException 401: If not connected to LinkedIn.
        HTTPException 400: If text is empty or too long.
        HTTPException 403: If CSRF validation fails or w_member_social scope missing.
        HTTPException 409: If duplicate publish detected (60-second dedup window).
        HTTPException 429: If LinkedIn rate limited (includes retry_after_seconds).
        HTTPException 502: If LinkedIn API call fails.
    """
```

This endpoint:
1. Validates the request body
2. If `save_as_draft` is true, creates or updates a Post row with `status="draft"` and returns (no CSRF required for save)
3. Validates CSRF token (nonce cookie + HMAC, same pattern as disconnect endpoint)
4. Pre-flight scope check: verifies `w_member_social` is in `OAuthToken.scopes`. If missing, returns 403 with message: "Your LinkedIn connection needs to be updated. Please reconnect in Settings to enable publishing."
5. Checks idempotency: hashes the post content, checks the dedup cache. If duplicate within 60 seconds, returns 409.
6. Gets a valid access token via `get_valid_access_token()`
7. Gets the member URN from `OAuthToken.linkedin_member_id`
8. Calls `linkedin_client.create_post()` with the text (async)
9. If `post_id` is provided (editing an existing draft), updates that row. Otherwise creates a new Post row:
   - `linkedin_post_id` = activity ID from URN
   - `post_url` = constructed URL
   - `content` = full post text
   - `status` = "published"
   - `post_date` = today
   - `title` = first 100 chars of text (or provided title)
   - `draft_id` = provided draft_id (if any)
10. Returns the post ID, LinkedIn URL, and status
11. On `LinkedInRateLimitError`: returns 429 with `retry_after_seconds` in response body

**Rate limits (documented):** LinkedIn enforces 150 requests/member/day and 100,000 requests/application/day (UTC reset). A single user posting 1-5 times per week will not approach these limits, but the endpoint handles 429 responses gracefully.

#### GET /api/drafts

Lists available draft files from the configured drafts directory.

```python
@router.get("/api/drafts")
async def list_drafts() -> dict[str, Any]:
    """List LinkedIn draft files from the drafts directory.

    Returns:
        JSON with list of draft objects (draft_id, filename, title).
    """
```

#### GET /api/drafts/{filename}

Reads a specific draft file's content (with frontmatter stripped).

```python
@router.get("/api/drafts/{filename}")
async def get_draft(filename: str) -> dict[str, Any]:
    """Read a draft file's content.

    Path traversal is prevented by resolving the path and checking
    it is within the configured drafts directory using Path.is_relative_to().

    Returns:
        JSON with filename, title, draft_id, and content (frontmatter stripped).

    Raises:
        HTTPException 404: If the file is not found.
        HTTPException 400: If the filename contains path traversal.
    """
```

#### PATCH /api/posts/{post_id} (existing, enhanced)

Add `content` and `status` to the updateable fields:

```python
# Add to existing update_post() parameters:
content: str | None = Body(None),
status: str | None = Query(None, pattern="^(draft|published|analytics_linked)$"),
```

### 7. Page Routes

#### GET /dashboard/compose

Renders the Post Composer page.

```python
@router.get("/dashboard/compose", response_class=HTMLResponse)
async def compose(
    request: Request,
    draft: str | None = None,     # Optional draft filename to pre-load
    post_id: int | None = None,   # Optional post ID to edit a draft
    db: Session = Depends(get_session),
) -> HTMLResponse:
    """Render the post composer page.

    If ?draft=filename is provided, pre-loads the draft content (frontmatter stripped).
    If ?post_id=N is provided, pre-loads a saved draft post for editing.

    The Publish button is only enabled when:
    1. OAuth is connected
    2. w_member_social is in the stored scopes
    If either condition fails, a message explains what to do.
    """
```

#### GET /dashboard/posts

Renders the Posts browser / timeline page.

```python
@router.get("/dashboard/posts", response_class=HTMLResponse)
async def posts_browser(
    request: Request,
    status_filter: str | None = None,  # Filter by status
    db: Session = Depends(get_session),
) -> HTMLResponse:
    """Render the posts browser with unified timeline."""
```

### 8. Templates

#### compose.html (NEW)

The composer page includes:
- **Text area:** Full-width, dark-themed, with character count (live counter, turns amber at 2700, red at 3000)
- **Title field:** Optional, for dashboard display (auto-derived from first line if not provided)
- **Draft selector:** Dropdown showing available drafts from `~/bksp/drafts/linkedin/`. Selecting a draft loads its content into the text area via AJAX.
- **Visibility toggle:** PUBLIC (default) or CONNECTIONS
- **Action buttons:**
  - "Save Draft" (stores locally, does not publish)
  - "Publish to LinkedIn" (publishes via API, with confirmation dialog). **Disabled after first click** with loading spinner to prevent double-submit. Re-enabled only on error response.
- **Status area:** Shows success/error messages, LinkedIn post URL after publishing. For 429 responses, shows "Rate limited. Try again in X seconds." with the retry_after value from the server.
- **LinkedIn connection status:** If not connected, shows a message linking to Settings. If connected but `w_member_social` scope is missing, shows "Your LinkedIn connection needs to be updated. Please reconnect in Settings to enable publishing." The Publish button is disabled in both cases.
- **Preview panel:** Shows the text as it will appear (plain text, no markdown rendering). Displays approximate line count and a "LinkedIn-style" text preview with proper line breaks.
- **CSRF token:** Included as a hidden field, generated from the same nonce+HMAC pattern as the disconnect endpoint.

**JavaScript functions for compose page:**
- `updateCharCount()`: Live character counter, color changes at thresholds
- `loadDraft(filename)`: AJAX GET to `/api/drafts/{filename}`, populates text area
- `publishPost()`: Disables button, shows spinner, AJAX POST to `/api/posts/publish` with CSRF token. On success: shows URL, keeps button disabled. On 429: shows retry message with countdown. On other error: re-enables button, shows error.
- `saveDraft()`: AJAX POST to `/api/posts/publish` with `save_as_draft=true`
- `updatePreview()`: Mirrors text area content to preview panel

#### posts.html (NEW)

The posts browser page includes:
- **Filter bar:** Filter by status (All, Draft, Published, Linked, Imported)
- **Post cards:** Each post shows:
  - Title / first line of content
  - Date
  - Status badge (color-coded: blue=draft, green=published, gold=linked, gray=imported)
  - Analytics summary (impressions, engagements, saves, sends) if available
  - Draft ID badge if linked to a draft file
  - LinkedIn post URL (external link icon) if published
- **Sort:** By date (default), by impressions, by engagement rate
- **Draft files section:** Separate section showing unlinked drafts from `~/bksp/drafts/linkedin/` that are not yet associated with any post. Each has a "Compose" button that opens the composer with the draft pre-loaded.

#### post_detail.html (MODIFIED)

Add:
- **Content section:** If `post.content` is not null, display the full post text in a styled card above the metrics
- **Status badge:** Show the post status (draft, published, analytics_linked, imported) with appropriate color
- **Publish button:** If status is "draft", show a "Publish to LinkedIn" button that calls the publish API
- **Draft file link:** If `post.draft_id` is set and the draft file exists, show a link/path to the draft file
- **New metrics row:** Show saves, sends, profile_views, followers_gained, reposts (if any are non-null) in a secondary metrics card below the existing metrics
- **Per-post demographics:** If `post.demographics` is non-empty, display a demographics breakdown section with category headers (Company Size, Job Title, Location, Company) and bar charts showing percentages

#### base.html (MODIFIED)

Add two new nav items to the sidebar, positioned between "Dashboard" and "Analytics":

```python
("/dashboard/compose",  "Compose",    "M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"),
("/dashboard/posts",    "Posts",      "M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2"),
```

### 9. XLSX Import Enhancement

#### Aggregate Export (existing, enhanced)

The existing `_upsert_post` function in `ingest.py` already matches by `linkedin_post_id` first. No changes needed for basic URN matching.

Enhance it to preserve locally-stored content when an XLSX import matches an existing post:

```python
# In _upsert_post, when updating an existing post:
if existing:
    # ... existing metric updates ...

    # Preserve locally-stored content (never overwrite with None from XLSX)
    # Update status to analytics_linked if the post was published via API
    if existing.status == "published" and existing.content:
        existing.status = "analytics_linked"

    return existing
```

This ensures that when XLSX data arrives for a post that was published via the composer, the post transitions from "published" to "analytics_linked" status, and the locally-stored content is preserved.

#### Per-Post XLSX Import (NEW)

New parser function in `ingest.py` that handles the per-post XLSX format. Auto-detected by sheet names.

```python
def _detect_xlsx_format(wb: openpyxl.Workbook) -> str:
    """Detect XLSX export format by sheet names.

    Returns:
        "per_post" if PERFORMANCE and TOP DEMOGRAPHICS sheets present.
        "aggregate" if DISCOVERY and ENGAGEMENT sheets present.
        "unknown" otherwise.
    """
    sheet_names = {s.lower() for s in wb.sheetnames}
    if "performance" in sheet_names and "top demographics" in sheet_names:
        return "per_post"
    if "discovery" in sheet_names and "engagement" in sheet_names:
        return "aggregate"
    return "unknown"


def _parse_per_post_performance(ws) -> dict:
    """Parse key-value pairs from the PERFORMANCE sheet.

    The PERFORMANCE sheet uses a key-value layout (not tabular):
    - Row 1 (0-indexed): Post URL = https://...urn:li:share:1234
    - Row 2: Post Date = Feb 25, 2026
    - Row 3: Post Publish Time = 11:53 AM
    - Row 5+: Metric = value pairs (Impressions, Reactions, etc.)

    Values in column B are strings (including commas in numbers like "1,316").
    """
    data = {}
    for row in ws.iter_rows(min_row=1, max_col=2, values_only=True):
        if row[0] and row[1] is not None:
            key = str(row[0]).strip()
            val = str(row[1]).strip()
            data[key] = val
    return data


def _parse_int_with_commas(s: str) -> int:
    """Parse integer string that may contain commas. Returns 0 on failure."""
    try:
        return int(s.replace(",", ""))
    except (ValueError, AttributeError):
        return 0


def _parse_post_hour(time_str: str) -> int | None:
    """Parse post hour from LinkedIn time format (e.g., '11:53 AM').

    Returns hour in 24-hour format (0-23), or None on failure.
    """
    try:
        from datetime import datetime as dt
        t = dt.strptime(time_str.strip(), "%I:%M %p")
        return t.hour
    except (ValueError, AttributeError):
        return None


def _extract_urn_from_url(url: str) -> str | None:
    """Extract the numeric share ID from a LinkedIn post URL.

    Handles URLs containing urn:li:share:{id} or urn:li:activity:{id}.
    """
    match = re.search(r"urn:li:(?:share|activity):(\d+)", url)
    return match.group(1) if match else None


def _parse_per_post_demographics(ws) -> list[dict]:
    """Parse the TOP DEMOGRAPHICS sheet.

    Tabular format: Category | Value | Percentage
    Categories: "Company size", "Job title", "Location", "Company"
    Percentages are floats (0.31) or strings ("< 1%").
    """
    rows = []
    for row in ws.iter_rows(min_row=2, max_col=3, values_only=True):
        if not row[0] or row[1] is None:
            continue
        category = str(row[0]).strip().lower().replace(" ", "_")
        value = str(row[1]).strip()
        pct_raw = row[2]
        if isinstance(pct_raw, (int, float)):
            percentage = float(pct_raw)
        elif isinstance(pct_raw, str) and "<" in pct_raw:
            percentage = 0.005  # "< 1%" stored as 0.5%
        else:
            try:
                percentage = float(str(pct_raw).strip().rstrip("%")) / 100
            except (ValueError, AttributeError):
                percentage = 0.0
        rows.append({
            "category": category,
            "value": value,
            "percentage": percentage,
        })
    return rows


def ingest_per_post_xlsx(db: Session, wb: openpyxl.Workbook) -> dict:
    """Ingest a per-post XLSX export.

    Extracts metrics, post_hour, linkedin_post_id, and demographics
    from the per-post export format.

    Returns a dict with import results (post_id, metrics updated, demographics count).
    """
    perf_ws = wb["PERFORMANCE"]
    demo_ws = wb["TOP DEMOGRAPHICS"]

    # Parse performance data
    perf = _parse_per_post_performance(perf_ws)

    post_url = perf.get("Post URL", "")
    linkedin_post_id = _extract_urn_from_url(post_url)
    post_hour = _parse_post_hour(perf.get("Post Publish Time", ""))

    # Parse metrics
    metrics = {
        "impressions": _parse_int_with_commas(perf.get("Impressions", "0")),
        "members_reached": _parse_int_with_commas(perf.get("Members reached", "0")),
        "reactions": _parse_int_with_commas(perf.get("Reactions", "0")),
        "comments": _parse_int_with_commas(perf.get("Comments", "0")),
        "reposts": _parse_int_with_commas(perf.get("Reposts", "0")),
        "saves": _parse_int_with_commas(perf.get("Saves", "0")),
        "sends": _parse_int_with_commas(perf.get("Sends on LinkedIn", "0")),
        "profile_views": _parse_int_with_commas(
            perf.get("Profile viewers from this post", "0")
        ),
        "followers_gained": _parse_int_with_commas(
            perf.get("Followers gained from this post", "0")
        ),
    }

    # Find or create the post
    existing = None
    if linkedin_post_id:
        existing = db.query(Post).filter(
            Post.linkedin_post_id == linkedin_post_id
        ).first()

    if existing:
        post = existing
        # Update metrics (per-post export has more granular data)
        for key, val in metrics.items():
            if hasattr(post, key):
                setattr(post, key, val)
        if post_hour is not None:
            post.post_hour = post_hour
        if post.status == "published" and post.content:
            post.status = "analytics_linked"
    else:
        # Create new post from per-post export
        post_date_str = perf.get("Post Date", "")
        try:
            from datetime import datetime as dt
            post_date = dt.strptime(post_date_str, "%b %d, %Y").date()
        except (ValueError, AttributeError):
            from datetime import date
            post_date = date.today()

        post = Post(
            linkedin_post_id=linkedin_post_id,
            post_url=post_url if post_url else None,
            post_date=post_date,
            post_hour=post_hour,
            **{k: v for k, v in metrics.items() if hasattr(Post, k)},
        )
        post.recalculate_engagement_rate()
        db.add(post)
        db.flush()  # Get post.id for demographics FK

    # Parse and store demographics
    demo_rows = _parse_per_post_demographics(demo_ws)
    demo_count = 0
    for row in demo_rows:
        existing_demo = db.query(PostDemographic).filter(
            PostDemographic.post_id == post.id,
            PostDemographic.category == row["category"],
            PostDemographic.value == row["value"],
        ).first()
        if existing_demo:
            existing_demo.percentage = row["percentage"]
        else:
            db.add(PostDemographic(
                post_id=post.id,
                category=row["category"],
                value=row["value"],
                percentage=row["percentage"],
            ))
            demo_count += 1

    db.commit()

    return {
        "post_id": post.id,
        "linkedin_post_id": linkedin_post_id,
        "metrics_updated": True,
        "demographics_imported": demo_count,
    }
```

**Batch import:** The existing upload endpoint accepts a single file. To support uploading multiple per-post XLSX files at once, add a `POST /api/upload/batch` endpoint that accepts multiple files and calls `ingest_per_post_xlsx` for each. The upload form is updated to allow multiple file selection (`<input type="file" multiple>`). Each file is processed independently; partial failures do not block other files.

### 10. LinkedIn Post URN Format and ID Matching (RESOLVED)

The URN mismatch concern from the red team review (finding #1) and feasibility review (C1) is now **resolved** by the discovery of LinkedIn's per-post XLSX export format.

**Previous concern:** The aggregate XLSX export URLs contain `urn:li:activity:{id}`, while the Posts API returns `urn:li:share:{id}` or `urn:li:ugcPost:{id}`. The numeric IDs across these URN types are different for the same post, so matching by numeric ID alone would fail.

**Resolution:** The per-post XLSX export's PERFORMANCE sheet contains a "Post URL" field with the full URL including `urn:li:share:{id}`. For example:
```
Post URL = https://www.linkedin.com/feed/update/urn:li:share:7432391508978397184
```

This is the same URN format returned by the Posts API's `x-restli-id` header. The `linkedin_post_id` column stores the numeric portion of the `urn:li:share:{id}` URN, which matches between the API response and the per-post XLSX export.

**For aggregate XLSX imports:** The existing `_extract_activity_id` function extracts from `urn:li:activity:{id}` URLs. The activity URN's numeric ID is different from the share URN's numeric ID for the same post. Aggregate import matching still works for posts that were originally imported from aggregate exports (they match on their own activity ID). For posts published via the API (which store the share ID), the per-post XLSX export provides the matching share URN.

**Summary of ID matching strategy:**
- Posts published via API: `linkedin_post_id` = share ID from `urn:li:share:{id}`
- Posts imported from per-post XLSX: `linkedin_post_id` = share ID from `urn:li:share:{id}` (same format)
- Posts imported from aggregate XLSX: `linkedin_post_id` = activity ID from `urn:li:activity:{id}` (different number)
- Matching between API-published posts and per-post XLSX imports: exact match on share ID
- Matching between API-published posts and aggregate XLSX imports: no automatic match (different ID spaces). The per-post XLSX import is the recommended path for linking API-published posts to analytics.

---

## Interfaces / Schema Changes

### Modified Table: `posts`

| Column | Type | Constraints | Description |
|---|---|---|---|
| content | TEXT | NULLABLE | Full post body text (stored when composed in dashboard) |
| status | VARCHAR(20) | NULLABLE | Lifecycle status: draft, published, analytics_linked, or NULL (imported) |
| saves | INTEGER | NULLABLE, DEFAULT 0 | Post saves (from per-post XLSX export) |
| sends | INTEGER | NULLABLE, DEFAULT 0 | Post sends on LinkedIn (from per-post XLSX export) |
| profile_views | INTEGER | NULLABLE, DEFAULT 0 | Profile viewers from this post (from per-post XLSX export) |
| followers_gained | INTEGER | NULLABLE, DEFAULT 0 | Followers gained from this post (from per-post XLSX export) |
| reposts | INTEGER | NULLABLE, DEFAULT 0 | Reposts (distinct from shares in aggregate export) |

### New Table: `post_demographics`

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | INTEGER | PK, AUTOINCREMENT | Primary key |
| post_id | INTEGER | FK(posts.id), NOT NULL | Parent post |
| category | VARCHAR | NOT NULL | Demographic category: company_size, job_title, location, company |
| value | VARCHAR | NOT NULL | Category value (e.g., "Software Engineer", "10,001+ employees") |
| percentage | FLOAT | NOT NULL | Percentage as decimal (0.31 = 31%) |
| created_at | DATETIME | DEFAULT now() | Row creation timestamp |

Unique constraint: `(post_id, category, value)`.

### New Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `DRAFTS_DIR` | No (Yes in Docker) | `~/bksp/drafts/linkedin` | Path to LinkedIn draft markdown files. Docker: mount as volume, set env var. |

### New API Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/posts/publish` | Publish a post to LinkedIn (or save as draft). CSRF protected. |
| GET | `/api/drafts` | List available draft files |
| GET | `/api/drafts/{filename}` | Read a draft file's content (frontmatter stripped) |
| POST | `/api/upload/batch` | Upload multiple per-post XLSX files at once |

### New Page Routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/dashboard/compose` | Post composer page |
| GET | `/dashboard/posts` | Posts browser / timeline |

### Modified API Endpoints

| Method | Path | Change |
|---|---|---|
| PATCH | `/api/posts/{post_id}` | Add `content` and `status` fields |
| GET | `/api/posts` | Include `content` (truncated to 200 chars with `...` suffix), `status`, `saves`, `sends`, `profile_views`, `followers_gained`, `reposts` in response |
| GET | `/api/posts/{post_id}` | Include full `content`, `status`, new metrics, and `demographics` list in response |
| POST | `/api/upload` | Auto-detect XLSX format (per-post vs aggregate) and route to appropriate parser |

### OAuth Scope Change

| Before | After | Impact |
|---|---|---|
| `openid profile` | `openid profile w_member_social` | Users must re-authorize after deployment |

---

## Data Migration

### Migration Script: `scripts/migrate_002_post_content.py`

Adds `content` (TEXT), `status` (VARCHAR(20)), `saves` (INTEGER), `sends` (INTEGER), `profile_views` (INTEGER), `followers_gained` (INTEGER), and `reposts` (INTEGER) columns to the existing `posts` table. Creates the `post_demographics` table. Follows the idempotent pattern from `scripts/migrate_001_cohort_columns.py`.

```python
"""Add content, status, and per-post metric columns to posts table.
Create post_demographics table.

Run once after deploying this feature:
    python scripts/migrate_002_post_content.py

Idempotent: safe to run multiple times (checks for column/table existence).
"""

import sqlite3

from app.config import settings


def migrate() -> None:
    conn = sqlite3.connect(str(settings.db_path))
    cursor = conn.cursor()

    # Add new columns to posts table
    cursor.execute("PRAGMA table_info(posts)")
    existing = {row[1] for row in cursor.fetchall()}

    post_columns = [
        ("content", "TEXT"),
        ("status", "VARCHAR(20)"),
        ("saves", "INTEGER"),
        ("sends", "INTEGER"),
        ("profile_views", "INTEGER"),
        ("followers_gained", "INTEGER"),
        ("reposts", "INTEGER"),
    ]

    for col_name, col_type in post_columns:
        if col_name not in existing:
            cursor.execute(
                f"ALTER TABLE posts ADD COLUMN {col_name} {col_type}"
            )
            print(f"Added column: posts.{col_name}")
        else:
            print(f"Column already exists: posts.{col_name}")

    # Create post_demographics table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS post_demographics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL REFERENCES posts(id),
            category VARCHAR NOT NULL,
            value VARCHAR NOT NULL,
            percentage FLOAT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(post_id, category, value)
        )
    """)
    print("Ensured post_demographics table exists.")

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
```

For fresh installs, `Base.metadata.create_all()` handles the new columns and table automatically. The migration script is only needed for existing databases.

**Rollback procedure:** If rollback is needed, the following SQL removes the new schema (requires SQLite 3.35.0+ for `DROP COLUMN`):

```sql
ALTER TABLE posts DROP COLUMN content;
ALTER TABLE posts DROP COLUMN status;
ALTER TABLE posts DROP COLUMN saves;
ALTER TABLE posts DROP COLUMN sends;
ALTER TABLE posts DROP COLUMN profile_views;
ALTER TABLE posts DROP COLUMN followers_gained;
ALTER TABLE posts DROP COLUMN reposts;
DROP TABLE IF EXISTS post_demographics;
```

---

## Rollout Plan

### Phase 0: API Endpoint Verification (manual, before implementation)

0. **Back up the database** (`cp linkedin.db linkedin.db.bak`)
1. Test whether the existing LinkedIn developer app can call `POST https://api.linkedin.com/rest/posts` with the `w_member_social` token from the "Share on LinkedIn" product.
2. If `/rest/posts` returns 403, test `POST https://api.linkedin.com/v2/ugcPosts` with the same token.
3. Document which endpoint works. If only `/v2/ugcPosts` works, implement the alternate payload format described in Section 3.
4. Record the result in a comment at the top of `linkedin_client.py`.

### Phase 1: Schema and API Client (backend only)

1. Add `content`, `status`, `saves`, `sends`, `profile_views`, `followers_gained`, `reposts` columns to `Post` model in `models.py`
2. Add `PostDemographic` model to `models.py`
3. Create `scripts/migrate_002_post_content.py`
4. Add `drafts_dir` setting to `config.py`
5. Create `app/linkedin_client.py` with async `create_post()` and `get_member_id()`
6. Update `_SCOPES` in `oauth.py` to include `w_member_social`
7. Restructure OAuth callback in `oauth_routes.py`: fetch member ID before `store_tokens()`, pass both to `store_tokens()` in a single call
8. Write tests for `linkedin_client.py`

### Phase 2: API Endpoints and Import

9. Add draft reader functions (list, read with frontmatter stripping) to a new section in `api.py`
10. Add `POST /api/posts/publish` endpoint with CSRF protection, scope check, and dedup
11. Add `POST /api/upload/batch` endpoint for multiple per-post XLSX files
12. Add per-post XLSX detection and parser to `ingest.py`
13. Enhance `PATCH /api/posts/{post_id}` with `content` and `status` fields
14. Update `_serialize_post` to include `content` (truncated: `content[:200] + "..." if len(content) > 200 else content`), `status`, new metrics, and demographics
15. Update `_upsert_post` in `ingest.py` to handle status transition
16. Write tests for new endpoints and per-post import

### Phase 3: UI Pages

17. Create `app/templates/compose.html` with JavaScript functions (char count, draft loading, publish with button disable, CSRF token, 429 handling)
18. Create `app/templates/posts.html`
19. Update `app/templates/post_detail.html` with content display, status badge, new metrics, per-post demographics
20. Update `app/templates/base.html` with new nav items
21. Add compose and posts browser routes to `dashboard.py`
22. Write route tests

### Phase 4: Polish and Deploy

23. Back up database (`cp linkedin.db linkedin.db.bak`)
24. Run migration script on existing database
25. Re-authorize LinkedIn account (for new `w_member_social` scope)
26. Test end-to-end: compose, publish, verify URN stored, import per-post XLSX, verify linkage and demographics
27. Docker compose rebuild and deploy (include `DRAFTS_DIR` volume mount)

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `w_member_social` scope not available without Community Management API | Low | High (blocks publishing) | LinkedIn documentation confirms `w_member_social` comes with "Share on LinkedIn" product, which is auto-granted. Verified in developer portal. Phase 0 confirms endpoint access before building. |
| `/rest/posts` requires Marketing API access, not just `w_member_social` | Medium | Medium (requires endpoint switch) | Phase 0 tests both `/rest/posts` and `/v2/ugcPosts`. The implementation supports both payload formats. If `/rest/posts` returns 403, fall back to `/v2/ugcPosts`. |
| URN format mismatch between API response and aggregate XLSX export | Known | Low (mitigated) | Per-post XLSX export uses `urn:li:share:{id}`, same as API response. Aggregate export uses `urn:li:activity:{id}` (different number). Per-post import is the recommended path for linking API-published posts. See Section 10. |
| LinkedIn member ID not available from /v2/userinfo | Low | High (cannot construct author URN) | The `sub` claim is a standard OIDC field. If unavailable, fall back to prompting the user to enter their member ID manually in Settings. |
| Rate limiting on Posts API | Low | Low (single user, infrequent posts) | LinkedIn rate limits: 150 requests/member/day, 100,000/app/day. Single user posting 1-5/week will not approach limits. 429 responses handled with Retry-After header parsing and user-friendly message. |
| LinkedIn API version deprecation | Medium | Medium | API version is pinned in config (`LINKEDIN_API_VERSION`). When LinkedIn deprecates a version, update the config value. No code changes needed. |
| User accidentally publishes a draft | Medium | Medium (post goes live on LinkedIn) | Confirmation dialog before publishing. Publish button disabled after click. Server-side 60-second dedup window prevents double-publish. No bulk publish in v1. |
| Draft files moved or renamed outside the app | Low | Low | Drafts are read at request time, not cached. If a file disappears, it simply stops showing in the list. No data loss. |
| Large post content in database | Low | Low | LinkedIn caps posts at 3000 chars. TEXT column handles this easily. Truncate to 200 chars with `...` suffix in list views. |
| Re-authorization required after scope change | Certain | Low | One-time action. Settings page already handles reconnection. Document in release notes. |
| Per-post XLSX format changes | Low | Medium | Format is auto-detected by sheet names. Key-value parsing is tolerant of missing rows. Demographics parser skips unrecognized categories. |

---

## Test Plan

### Test Command

```bash
cd ~/bksp.ca/linkedin-analytics && python -m pytest tests/ -v
```

### Unit Tests: LinkedIn Client (`tests/test_linkedin_client.py`)

1. **`test_create_post_success`**: Mock async httpx.post returning 201 with `x-restli-id` header. Verify PublishResult fields.
2. **`test_create_post_empty_text_raises`**: Verify ValueError for empty text.
3. **`test_create_post_text_too_long_raises`**: Verify ValueError for text > 3000 chars.
4. **`test_create_post_api_error_sanitized`**: Mock httpx.post returning 403. Verify LinkedInAPIError with sanitized message (no token in error).
5. **`test_create_post_rate_limited`**: Mock httpx.post returning 429 with Retry-After header. Verify LinkedInRateLimitError with retry_after_seconds.
6. **`test_create_post_network_error_sanitized`**: Mock httpx.post raising httpx.ConnectError. Verify LinkedInAPIError.
7. **`test_create_post_missing_restli_id`**: Mock httpx.post returning 201 but no `x-restli-id` header. Verify LinkedInAPIError.
8. **`test_extract_activity_id_share_urn`**: Verify extraction from `urn:li:share:123`.
9. **`test_extract_activity_id_ugcpost_urn`**: Verify extraction from `urn:li:ugcPost:456`.
10. **`test_extract_activity_id_activity_urn`**: Verify extraction from `urn:li:activity:789`.
11. **`test_extract_activity_id_invalid`**: Verify None for invalid URN.
12. **`test_build_headers`**: Verify Authorization, LinkedIn-Version, X-Restli-Protocol-Version, Content-Type headers.
13. **`test_get_member_id_success`**: Mock async httpx.get returning userinfo with `sub`. Verify member ID returned.
14. **`test_get_member_id_failure_returns_none`**: Mock httpx.get raising error. Verify None returned (non-fatal).

### Route Tests: Publish Flow (`tests/test_compose.py`)

1. **`test_publish_creates_post_in_db`**: Mock LinkedIn API, POST `/api/posts/publish` with CSRF token, verify Post row created with correct fields.
2. **`test_publish_stores_linkedin_post_id`**: Verify `linkedin_post_id` matches the extracted share ID from the mocked `x-restli-id` header.
3. **`test_publish_stores_content`**: Verify `content` column contains the full post text.
4. **`test_publish_sets_status_published`**: Verify `status` is "published".
5. **`test_publish_returns_linkedin_url`**: Verify response includes the constructed LinkedIn post URL.
6. **`test_publish_requires_oauth_connection`**: Without tokens in DB, POST `/api/posts/publish` returns 401.
7. **`test_publish_requires_member_id`**: With tokens but no member_id, verify appropriate error.
8. **`test_publish_empty_text_returns_400`**: POST with empty text, verify 400.
9. **`test_publish_text_too_long_returns_400`**: POST with text > 3000 chars, verify 400.
10. **`test_publish_missing_csrf_returns_403`**: POST without CSRF token, verify 403.
11. **`test_publish_missing_scope_returns_403`**: Tokens present but `w_member_social` not in scopes, verify 403 with re-authorization message.
12. **`test_publish_duplicate_returns_409`**: POST same content twice within 60 seconds, verify 409 on second attempt.
13. **`test_publish_rate_limited_returns_429`**: Mock LinkedIn returning 429, verify response includes `retry_after_seconds`.
14. **`test_publish_updates_existing_draft`**: POST with `post_id` of an existing draft, verify the draft row is updated (not a new row created).
15. **`test_save_as_draft_does_not_call_api`**: POST with `save_as_draft=true`, verify no LinkedIn API call made and status is "draft".
16. **`test_save_as_draft_stores_content`**: Verify draft content is stored.
17. **`test_compose_page_renders`**: GET `/dashboard/compose`, verify 200.
18. **`test_compose_page_with_draft_param`**: GET `/dashboard/compose?draft=001-commitment-without-execution.md`, verify draft content pre-loaded (mock file) with frontmatter stripped.
19. **`test_posts_browser_renders`**: GET `/dashboard/posts`, verify 200.
20. **`test_posts_browser_shows_status_filter`**: GET `/dashboard/posts?status_filter=published`, verify filtered results.

### Route Tests: Drafts API (`tests/test_compose.py`)

21. **`test_list_drafts_empty_dir`**: With no drafts directory, GET `/api/drafts` returns empty list.
22. **`test_list_drafts_filters_review_files`**: With draft + review files, verify only main drafts returned.
23. **`test_read_draft_success`**: GET `/api/drafts/001-commitment-without-execution.md`, verify content returned with frontmatter stripped.
24. **`test_read_draft_path_traversal_blocked`**: GET `/api/drafts/../../etc/passwd`, verify 400. Uses `Path.is_relative_to()`.
25. **`test_read_draft_not_found`**: GET `/api/drafts/nonexistent.md`, verify 404.

### Per-Post XLSX Import Tests (`tests/test_per_post_ingest.py`)

26. **`test_detect_per_post_format`**: Workbook with PERFORMANCE + TOP DEMOGRAPHICS sheets detected as "per_post".
27. **`test_detect_aggregate_format`**: Workbook with DISCOVERY + ENGAGEMENT sheets detected as "aggregate".
28. **`test_parse_per_post_performance`**: Verify key-value extraction from PERFORMANCE sheet, including comma-separated numbers.
29. **`test_parse_post_hour`**: Verify "11:53 AM" -> 11, "2:30 PM" -> 14.
30. **`test_extract_urn_from_url`**: Verify extraction of share ID from LinkedIn post URL.
31. **`test_parse_per_post_demographics`**: Verify category/value/percentage extraction from TOP DEMOGRAPHICS sheet.
32. **`test_parse_demographics_less_than_one_percent`**: Verify "< 1%" is stored as 0.005.
33. **`test_ingest_per_post_creates_post`**: Full ingest of per-post XLSX creates Post with correct metrics and demographics.
34. **`test_ingest_per_post_updates_existing`**: Per-post XLSX for an existing post updates metrics and adds demographics.
35. **`test_ingest_per_post_extracts_new_metrics`**: Verify saves, sends, profile_views, followers_gained, reposts are stored.
36. **`test_batch_upload_multiple_files`**: POST `/api/upload/batch` with 3 per-post XLSX files, verify all processed.

### Integration Tests: XLSX Import Linkage

37. **`test_xlsx_import_links_to_api_published_post`**: Create a post via publish API (mocked), then import per-post XLSX with matching `linkedin_post_id`. Verify the post's status becomes "analytics_linked" and analytics data is merged.
38. **`test_xlsx_import_preserves_content`**: After import, verify the post's `content` column is unchanged (not overwritten by XLSX which has no content).
39. **`test_per_post_demographics_stored_correctly`**: After per-post XLSX import, verify PostDemographic rows with correct category/value/percentage.

### Existing Tests (verify no regressions)

40. All existing tests in `test_routes.py`, `test_models.py`, `test_ingest.py`, `test_oauth.py`, `test_oauth_routes.py` continue to pass.

---

## Acceptance Criteria

1. **Compose page works:** User can navigate to `/dashboard/compose`, type post text, see a live character count, and either save as a draft or publish to LinkedIn.
2. **Post publishes to LinkedIn:** Clicking "Publish to LinkedIn" creates a real post on the user's LinkedIn feed. A confirmation dialog prevents accidental publishing. The publish button is disabled after click with a loading spinner.
3. **CSRF protection on publish:** The publish endpoint validates a CSRF token using the same nonce cookie + HMAC pattern as the disconnect endpoint. Requests without a valid CSRF token return 403.
4. **Scope pre-flight check:** If the stored OAuth token does not include `w_member_social`, the Publish button is disabled and a message explains how to reconnect.
5. **Idempotency protection:** Publishing the same content twice within 60 seconds returns 409. The publish button is disabled client-side after the first click.
6. **URN captured and stored:** After publishing, the LinkedIn post URN is extracted from the `x-restli-id` response header and stored in `linkedin_post_id`. The constructed post URL is stored in `post_url`.
7. **Content stored locally:** The post's full text is stored in the `content` column and is visible on the post detail page.
8. **Draft loading works:** Selecting a draft from `~/bksp/drafts/linkedin/` in the composer loads its content into the text area with YAML frontmatter stripped. The draft_id is automatically linked.
9. **Posts browser shows timeline:** `/dashboard/posts` displays all posts with status badges (draft, published, linked, imported) and allows filtering by status. Imported posts are filtered using `status IS NULL`.
10. **XLSX import links to API-published posts:** When a per-post XLSX export is imported and contains analytics for a post that was previously published via the API, the analytics data is merged and the status transitions to "analytics_linked."
11. **Per-post XLSX import:** Uploading a per-post XLSX file (auto-detected by PERFORMANCE + TOP DEMOGRAPHICS sheets) creates or updates a Post with saves, sends, profile_views, followers_gained, reposts, post_hour, and per-post demographics.
12. **Per-post demographics displayed:** The post detail page shows per-post demographics (company_size, job_title, location, company) with percentages when available from per-post XLSX import.
13. **Batch per-post import:** Multiple per-post XLSX files can be uploaded at once via `/api/upload/batch`.
14. **Graceful degradation:** If OAuth is not connected, the Compose page shows a "Connect LinkedIn first" message and the Publish button is disabled. The Save Draft and Posts Browser features still work.
15. **No token leakage:** Access tokens never appear in logs, URLs, HTML source, or JavaScript. API errors are sanitized per the linkedin-api-architect agent rules.
16. **Path traversal blocked:** The draft file reader only serves files from the configured `drafts_dir`, validated using `Path.is_relative_to()`. Attempts to read files outside that directory return 400.
17. **Rate limit handling:** If LinkedIn returns 429, the UI shows "Rate limited. Try again in X seconds." with the Retry-After value. No generic error displayed.
18. **Async API calls:** All LinkedIn API calls use `httpx.AsyncClient` to avoid blocking the FastAPI event loop.
19. **All tests pass:** `python -m pytest tests/ -v` passes with no failures.
20. **Phase 0 verified:** The working API endpoint (`/rest/posts` or `/v2/ugcPosts`) is documented in a comment at the top of `linkedin_client.py`.

---

## Task Breakdown

### Files to Create

| File | Purpose |
|---|---|
| `linkedin-analytics/app/linkedin_client.py` | LinkedIn REST API client: async create_post, get_member_id, header building, rate limit logging, 429 handling |
| `linkedin-analytics/app/templates/compose.html` | Post composer page: text area, character count, draft selector, publish/save buttons, CSRF token, button disable on submit |
| `linkedin-analytics/app/templates/posts.html` | Posts browser page: timeline view with status filters and post cards |
| `linkedin-analytics/scripts/migrate_002_post_content.py` | Add content, status, new metric columns to posts table; create post_demographics table |
| `linkedin-analytics/tests/test_linkedin_client.py` | Unit tests for LinkedIn API client (including 429 handling) |
| `linkedin-analytics/tests/test_compose.py` | Route tests for compose, publish (with CSRF, scope check, dedup), drafts API, and posts browser |
| `linkedin-analytics/tests/test_per_post_ingest.py` | Tests for per-post XLSX format detection, parsing, and import |

### Files to Modify

| File | Change |
|---|---|
| `linkedin-analytics/app/models.py` | Add `content` (Text), `status` (String(20)), `saves`, `sends`, `profile_views`, `followers_gained`, `reposts` (Integer) columns to Post model. Add `PostDemographic` model. |
| `linkedin-analytics/app/config.py` | Add `drafts_dir` setting (Path, default `~/bksp/drafts/linkedin`). Document Docker requirement. |
| `linkedin-analytics/app/oauth.py` | Update `_SCOPES` from `"openid profile"` to `"openid profile w_member_social"` |
| `linkedin-analytics/app/routes/oauth_routes.py` | Restructure callback: fetch member ID BEFORE `store_tokens()`, pass both to `store_tokens()` in single call |
| `linkedin-analytics/app/routes/api.py` | Add `POST /api/posts/publish` (with CSRF, scope check, dedup), `GET /api/drafts`, `GET /api/drafts/{filename}`, `POST /api/upload/batch`; update `_serialize_post` to include content/status/new metrics/demographics; add `content` and `status` to PATCH endpoint |
| `linkedin-analytics/app/routes/dashboard.py` | Add `GET /dashboard/compose` and `GET /dashboard/posts` routes |
| `linkedin-analytics/app/templates/base.html` | Add "Compose" and "Posts" nav items to sidebar |
| `linkedin-analytics/app/templates/post_detail.html` | Add content display section, status badge, publish button for drafts, new metrics row (saves, sends, profile_views, followers_gained, reposts), per-post demographics section |
| `linkedin-analytics/app/ingest.py` | Add `_detect_xlsx_format()`, `ingest_per_post_xlsx()`, per-post parsers. Enhance `_upsert_post` to transition status from "published" to "analytics_linked" when XLSX data arrives for an API-published post. Update upload endpoint to auto-detect format. |
| `linkedin-analytics/app/main.py` | No changes needed (new routes are in existing routers) |

### Implementation Order

1. `app/models.py` (add content, status, new metric columns; add PostDemographic model)
2. `scripts/migrate_002_post_content.py` (migration script)
3. `app/config.py` (add drafts_dir setting)
4. `app/linkedin_client.py` (async API client with 429 handling)
5. `app/oauth.py` (update _SCOPES)
6. `app/routes/oauth_routes.py` (restructure callback: member ID before store_tokens)
7. `app/routes/api.py` (publish endpoint with CSRF+scope+dedup, drafts endpoints, batch upload, serialize updates)
8. `app/ingest.py` (per-post XLSX detection and parser, status transition on aggregate import)
9. `app/routes/dashboard.py` (compose and posts browser routes)
10. `app/templates/base.html` (nav updates)
11. `app/templates/compose.html` (composer page with JS: char count, draft loading, publish with button disable, CSRF, 429 display)
12. `app/templates/posts.html` (posts browser page)
13. `app/templates/post_detail.html` (content display, status badge, new metrics, demographics)
14. `tests/test_linkedin_client.py` (API client tests including 429)
15. `tests/test_compose.py` (route and integration tests including CSRF, scope, dedup)
16. `tests/test_per_post_ingest.py` (per-post XLSX import tests)

---

<!-- Context Metadata
discovered_at: 2026-03-01T17:00:00Z
revised_at: 2026-03-01T23:00:00Z
claude_md_exists: true
recent_plans_consulted: linkedin-oauth-auth.md, engagement-analytics.md, linkedin-analytics-dashboard.md, bksp-social-cma-app.md
archived_plans_consulted: none
reviews_incorporated: dashboard-post-composer.redteam.md, dashboard-post-composer.review.md, dashboard-post-composer.feasibility.md
-->

## Status: APPROVED
