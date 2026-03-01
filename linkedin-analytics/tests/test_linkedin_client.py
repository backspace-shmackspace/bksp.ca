"""Tests for app/linkedin_client.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.linkedin_client import (
    MAX_POST_LENGTH,
    LinkedInAPIError,
    LinkedInRateLimitError,
    PublishResult,
    _build_headers,
    _extract_activity_id,
    create_post,
    get_member_id,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(
    status_code: int,
    headers: dict | None = None,
    json_body: dict | None = None,
) -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.headers = httpx.Headers(headers or {})
    if json_body is not None:
        resp.json.return_value = json_body
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# _extract_activity_id
# ---------------------------------------------------------------------------


def test_extract_activity_id_share_urn():
    assert _extract_activity_id("urn:li:share:123456789") == "123456789"


def test_extract_activity_id_ugcpost_urn():
    assert _extract_activity_id("urn:li:ugcPost:987654321") == "987654321"


def test_extract_activity_id_activity_urn():
    assert _extract_activity_id("urn:li:activity:111222333") == "111222333"


def test_extract_activity_id_invalid():
    assert _extract_activity_id("not-a-urn") is None
    assert _extract_activity_id("") is None


# ---------------------------------------------------------------------------
# _build_headers
# ---------------------------------------------------------------------------


def test_build_headers(monkeypatch):
    monkeypatch.setattr("app.linkedin_client.settings.linkedin_api_version", "202601")
    headers = _build_headers("test_token_abc")
    assert headers["Authorization"] == "Bearer test_token_abc"
    assert headers["LinkedIn-Version"] == "202601"
    assert headers["X-Restli-Protocol-Version"] == "2.0.0"
    assert headers["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# create_post
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_post_empty_text_raises():
    with pytest.raises(ValueError, match="empty"):
        await create_post("token", "urn:li:person:abc", "")


@pytest.mark.asyncio
async def test_create_post_whitespace_only_raises():
    with pytest.raises(ValueError, match="empty"):
        await create_post("token", "urn:li:person:abc", "   ")


@pytest.mark.asyncio
async def test_create_post_text_too_long_raises():
    long_text = "x" * (MAX_POST_LENGTH + 1)
    with pytest.raises(ValueError, match="exceeds"):
        await create_post("token", "urn:li:person:abc", long_text)


@pytest.mark.asyncio
async def test_create_post_success():
    """Mock POST returning 201 with x-restli-id header."""
    mock_resp = _make_response(
        201,
        headers={"x-restli-id": "urn:li:share:7432391508978397184"},
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("app.linkedin_client.httpx.AsyncClient", return_value=mock_client):
        result = await create_post(
            "test_token",
            "urn:li:person:abc123",
            "Hello LinkedIn!",
        )

    assert isinstance(result, PublishResult)
    assert result.post_urn == "urn:li:share:7432391508978397184"
    assert result.activity_id == "7432391508978397184"
    assert "7432391508978397184" in result.post_url


@pytest.mark.asyncio
async def test_create_post_api_error_sanitized():
    """Mock POST returning 403. Error message must not contain token."""
    mock_resp = _make_response(403)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("app.linkedin_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(LinkedInAPIError) as exc_info:
            await create_post("secret_token", "urn:li:person:abc", "Hello!")

    assert "secret_token" not in str(exc_info.value)
    assert "403" in str(exc_info.value) or "status" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_create_post_rate_limited():
    """Mock POST returning 429 with Retry-After header."""
    mock_resp = _make_response(
        429,
        headers={"Retry-After": "30"},
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("app.linkedin_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(LinkedInRateLimitError) as exc_info:
            await create_post("token", "urn:li:person:abc", "Hello!")

    assert exc_info.value.retry_after_seconds == 30


@pytest.mark.asyncio
async def test_create_post_network_error_sanitized():
    """Mock httpx.ConnectError. Must raise LinkedInAPIError."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    with patch("app.linkedin_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(LinkedInAPIError) as exc_info:
            await create_post("token", "urn:li:person:abc", "Hello!")

    assert "Connection refused" not in str(exc_info.value)
    assert "Network error" in str(exc_info.value) or "network" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_create_post_missing_restli_id():
    """Mock POST returning 201 but no x-restli-id header."""
    mock_resp = _make_response(201, headers={})

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("app.linkedin_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(LinkedInAPIError, match="post ID"):
            await create_post("token", "urn:li:person:abc", "Hello!")


# ---------------------------------------------------------------------------
# get_member_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_member_id_success():
    """Mock GET returning userinfo with 'sub' claim."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock(return_value=None)
    mock_resp.json.return_value = {
        "sub": "abc123xyz",
        "name": "Ian Murphy",
        "email": "ian@example.com",
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.linkedin_client.httpx.AsyncClient", return_value=mock_client):
        result = await get_member_id("test_token")

    assert result == "abc123xyz"


@pytest.mark.asyncio
async def test_get_member_id_failure_returns_none():
    """Mock GET raising an error. Must return None (non-fatal)."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

    with patch("app.linkedin_client.httpx.AsyncClient", return_value=mock_client):
        result = await get_member_id("test_token")

    assert result is None


@pytest.mark.asyncio
async def test_get_member_id_http_error_returns_none():
    """Mock GET returning 401. Must return None (non-fatal)."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 401
    mock_resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_resp
        )
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.linkedin_client.httpx.AsyncClient", return_value=mock_client):
        result = await get_member_id("test_token")

    assert result is None
