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

Phase 0 note: If /rest/posts returns 403, fall back to /v2/ugcPosts using
the ugc_post payload format. Set USE_UGC_POSTS=true in the environment to
switch endpoints without code changes.
"""

import logging
import re
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Primary REST Posts endpoint. If the app only has "Share on LinkedIn" product
# access and /rest/posts returns 403, use the legacy /v2/ugcPosts endpoint.
_POSTS_URL = "https://api.linkedin.com/rest/posts"
_UGCPOSTS_URL = "https://api.linkedin.com/v2/ugcPosts"
_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

# LinkedIn post character limit
MAX_POST_LENGTH = 3000


class LinkedInAPIError(Exception):
    """Raised when a LinkedIn API call fails. Message is sanitized."""


class LinkedInRateLimitError(LinkedInAPIError):
    """Raised when LinkedIn returns 429. Includes retry_after_seconds."""

    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


@dataclass
class PublishResult:
    """Result from publishing a post to LinkedIn."""

    post_urn: str       # Full URN (e.g., "urn:li:share:123456")
    activity_id: str    # Extracted numeric ID
    post_url: str       # Constructed LinkedIn post URL


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
    - urn:li:ugcPost:6844785523593134080
    - urn:li:activity:6844785523593134080
    """
    match = re.search(r"urn:li:(?:share|ugcPost|activity):(\d+)", urn)
    return match.group(1) if match else None


def _build_rest_payload(
    member_urn: str,
    text: str,
    visibility: str,
) -> dict:
    """Build the payload for POST /rest/posts."""
    return {
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


def _build_ugc_payload(
    member_urn: str,
    text: str,
    visibility: str,
) -> dict:
    """Build the payload for POST /v2/ugcPosts (legacy endpoint)."""
    ugc_visibility = "PUBLIC" if visibility == "PUBLIC" else "CONNECTIONS_ONLY"
    return {
        "author": member_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": ugc_visibility
        },
    }


async def create_post(
    access_token: str,
    member_urn: str,
    text: str,
    visibility: str = "PUBLIC",
) -> PublishResult:
    """Publish a text-only post to LinkedIn.

    Attempts /rest/posts first. If that endpoint returns 403 (access denied),
    retries with the legacy /v2/ugcPosts endpoint using the ugcPost payload.

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

    headers = _build_headers(access_token)

    # Try /rest/posts first, fall back to /v2/ugcPosts on 403
    endpoints_and_payloads = [
        (_POSTS_URL, _build_rest_payload(member_urn, text, visibility)),
        (_UGCPOSTS_URL, _build_ugc_payload(member_urn, text, visibility)),
    ]

    last_error: LinkedInAPIError | None = None

    for url, payload in endpoints_and_payloads:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=httpx.Timeout(15.0),
                )
            _log_rate_limits(response)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            logger.error("LinkedIn Posts API %s returned status %d", url, status)

            if status == 429:
                retry_after = e.response.headers.get("Retry-After")
                retry_seconds = (
                    int(retry_after)
                    if retry_after and retry_after.isdigit()
                    else None
                )
                raise LinkedInRateLimitError(
                    f"Rate limited by LinkedIn. Try again in {retry_seconds or 'a few'} seconds.",
                    retry_after_seconds=retry_seconds,
                ) from None

            if status == 403 and url == _POSTS_URL:
                logger.info(
                    "POST /rest/posts returned 403; retrying with /v2/ugcPosts"
                )
                last_error = LinkedInAPIError(f"LinkedIn returned status {status}")
                continue

            raise LinkedInAPIError(
                f"LinkedIn returned status {status}"
            ) from None

        except httpx.HTTPError:
            logger.error("LinkedIn Posts API call failed: network error")
            raise LinkedInAPIError(
                "Network error while publishing to LinkedIn"
            ) from None
        else:
            # Successful response
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

            post_url = f"https://www.linkedin.com/feed/update/{post_urn}/"
            logger.info("Published post: %s", post_url)

            return PublishResult(
                post_urn=post_urn,
                activity_id=activity_id,
                post_url=post_url,
            )

    # Both endpoints failed
    if last_error:
        raise last_error
    raise LinkedInAPIError("LinkedIn Posts API call failed after retrying both endpoints")


async def get_member_id(access_token: str) -> str | None:
    """Fetch the authenticated member's LinkedIn ID from /v2/userinfo.

    Returns the 'sub' claim from the userinfo response, which is the
    person identifier used to construct the author URN
    (urn:li:person:{sub}).

    Returns None if the call fails (non-fatal; the member ID is cached
    in OAuthToken.linkedin_member_id after the first successful fetch).

    Args:
        access_token: Valid OAuth access token.

    Returns:
        The LinkedIn member ID string, or None on failure.
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
        logger.warning(
            "Failed to fetch member ID from /userinfo: %s", type(e).__name__
        )
        return None
