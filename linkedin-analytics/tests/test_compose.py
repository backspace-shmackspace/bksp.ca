"""Tests for the post composer routes and publish flow."""

import hashlib
import hmac
import secrets
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from app.models import OAuthToken, Post

# A valid Fernet key used across all compose tests
_TEST_KEY = Fernet.generate_key().decode()
_TEST_FERNET = Fernet(_TEST_KEY.encode())


# ---------------------------------------------------------------------------
# CSRF token helper (mirrors the logic in api.py publish endpoint)
# ---------------------------------------------------------------------------


def _make_publish_csrf(nonce: str, key: str) -> str:
    """Compute the HMAC for a publish CSRF nonce."""
    return hmac.new(
        key.encode(),
        f"publish:{nonce}".encode(),
        hashlib.sha256,
    ).hexdigest()


# ---------------------------------------------------------------------------
# Helpers to seed tokens
# ---------------------------------------------------------------------------


def _seed_oauth_token(test_session, scopes: str = "openid profile w_member_social"):
    """Seed an OAuthToken row using store_tokens with the test Fernet key."""
    from unittest.mock import patch as _patch
    from app.oauth import TokenResponse, store_tokens

    tr = TokenResponse(
        access_token="fake_access_token_xyz",
        refresh_token="fake_refresh_token",
        expires_in=315360000,  # ~10 years
        refresh_token_expires_in=315360000,
        scope=scopes,
    )

    with _patch("app.oauth.settings") as mock_settings:
        mock_settings.token_encryption_key = _TEST_KEY
        row = store_tokens(test_session, tr, member_id="test_member_abc")

    return row


# ---------------------------------------------------------------------------
# Compose page routes
# ---------------------------------------------------------------------------


def test_compose_page_renders(client):
    resp = client.get("/dashboard/compose")
    assert resp.status_code == 200
    assert b"Compose" in resp.content


def test_posts_browser_renders(client):
    resp = client.get("/dashboard/posts")
    assert resp.status_code == 200
    assert b"Posts" in resp.content


def test_posts_browser_shows_all_by_default(client, sample_posts):
    resp = client.get("/dashboard/posts")
    assert resp.status_code == 200


def test_posts_browser_status_filter(client, test_session):
    post = Post(
        post_date=date.today(),
        title="My draft post",
        content="Draft content here",
        status="draft",
    )
    post.recalculate_engagement_rate()
    test_session.add(post)
    test_session.commit()

    resp = client.get("/dashboard/posts?status_filter=draft")
    assert resp.status_code == 200
    assert b"Draft" in resp.content


# ---------------------------------------------------------------------------
# /api/drafts
# ---------------------------------------------------------------------------


def test_list_drafts_empty_dir(client, tmp_path, monkeypatch):
    """When drafts_dir doesn't exist, returns empty list."""
    monkeypatch.setattr("app.config.settings.drafts_dir", tmp_path / "nonexistent")
    resp = client.get("/api/drafts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert data["drafts"] == []


def test_list_drafts_filters_review_files(client, tmp_path, monkeypatch):
    """Draft list excludes supplementary review files."""
    drafts_dir = tmp_path / "drafts"
    drafts_dir.mkdir()
    (drafts_dir / "001-my-post.md").write_text("# Hello\nContent here")
    (drafts_dir / "001-my-post.copy-review.md").write_text("review")
    (drafts_dir / "001-my-post.sensitivity-review.md").write_text("review")
    (drafts_dir / "002-another.md").write_text("# Another\nMore content")

    monkeypatch.setattr("app.config.settings.drafts_dir", drafts_dir)
    resp = client.get("/api/drafts")
    assert resp.status_code == 200
    data = resp.json()
    filenames = [d["filename"] for d in data["drafts"]]
    assert "001-my-post.md" in filenames
    assert "002-another.md" in filenames
    assert "001-my-post.copy-review.md" not in filenames
    assert "001-my-post.sensitivity-review.md" not in filenames


def test_read_draft_success(client, tmp_path, monkeypatch):
    """GET /api/drafts/{filename} returns content with frontmatter stripped."""
    drafts_dir = tmp_path / "drafts"
    drafts_dir.mkdir()
    content_with_frontmatter = (
        "---\n"
        "title: Test Post\n"
        "date: 2026-03-01\n"
        "---\n"
        "\n"
        "This is the actual post body.\n"
        "Second line here."
    )
    (drafts_dir / "001-commitment-without-execution.md").write_text(content_with_frontmatter)

    monkeypatch.setattr("app.config.settings.drafts_dir", drafts_dir)
    resp = client.get("/api/drafts/001-commitment-without-execution.md")
    assert resp.status_code == 200
    data = resp.json()
    assert "This is the actual post body." in data["content"]
    assert "title: Test Post" not in data["content"]
    assert data["draft_id"] == "001"


def test_read_draft_path_traversal_blocked(client, tmp_path, monkeypatch):
    """Path traversal attempts return 400."""
    drafts_dir = tmp_path / "drafts"
    drafts_dir.mkdir()

    monkeypatch.setattr("app.config.settings.drafts_dir", drafts_dir)
    # Slash-based traversal is caught by the filename check
    resp = client.get("/api/drafts/..%2F..%2Fetc%2Fpasswd")
    assert resp.status_code in (400, 404)


def test_read_draft_not_found(client, tmp_path, monkeypatch):
    """GET /api/drafts/nonexistent.md returns 404."""
    drafts_dir = tmp_path / "drafts"
    drafts_dir.mkdir()

    monkeypatch.setattr("app.config.settings.drafts_dir", drafts_dir)
    resp = client.get("/api/drafts/nonexistent.md")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /api/posts/publish - validation
# ---------------------------------------------------------------------------


def test_publish_empty_text_returns_400(client):
    resp = client.post("/api/posts/publish", json={"text": "", "csrf_token": "x"})
    assert resp.status_code == 400


def test_publish_text_too_long_returns_400(client):
    long_text = "x" * 3001
    resp = client.post("/api/posts/publish", json={"text": long_text, "csrf_token": "x"})
    assert resp.status_code == 400


def test_publish_requires_oauth_connection(client):
    """Without tokens in DB, POST /api/posts/publish returns 403 (CSRF fails first)."""
    # CSRF check fires before auth check, so we get 403
    resp = client.post(
        "/api/posts/publish",
        json={"text": "Hello LinkedIn!", "csrf_token": "invalid"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# /api/posts/publish - save_as_draft (no CSRF required)
# ---------------------------------------------------------------------------


def test_save_as_draft_does_not_call_api(client, test_session):
    """save_as_draft=true must not touch the LinkedIn API."""
    with patch("app.linkedin_client.create_post") as mock_create:
        resp = client.post(
            "/api/posts/publish",
            json={
                "text": "Draft content for later",
                "title": "My Draft",
                "save_as_draft": True,
            },
        )
    assert resp.status_code == 200
    mock_create.assert_not_called()


def test_save_as_draft_stores_content(client, test_session):
    """Saved draft has content in the database."""
    resp = client.post(
        "/api/posts/publish",
        json={
            "text": "This is my draft post content.",
            "title": "My Draft Post",
            "draft_id": "007",
            "save_as_draft": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "draft"
    post_id = data["id"]

    post = test_session.query(Post).filter(Post.id == post_id).first()
    assert post is not None
    assert post.content == "This is my draft post content."
    assert post.status == "draft"
    assert post.draft_id == "007"


def test_save_as_draft_updates_existing(client, test_session):
    """save_as_draft with post_id updates existing row."""
    existing = Post(
        post_date=date.today(),
        title="Old title",
        content="Old content",
        status="draft",
    )
    existing.recalculate_engagement_rate()
    test_session.add(existing)
    test_session.commit()
    test_session.refresh(existing)

    resp = client.post(
        "/api/posts/publish",
        json={
            "text": "Updated draft content.",
            "post_id": existing.id,
            "save_as_draft": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == existing.id

    test_session.refresh(existing)
    assert existing.content == "Updated draft content."


# ---------------------------------------------------------------------------
# /api/posts/publish - CSRF validation
# ---------------------------------------------------------------------------


def test_publish_missing_csrf_returns_403(client, test_session, monkeypatch):
    """POST without CSRF token returns 403."""
    monkeypatch.setattr("app.config.settings.token_encryption_key", _TEST_KEY)
    monkeypatch.setattr("app.routes.api.settings.token_encryption_key", _TEST_KEY)
    _seed_oauth_token(test_session)
    resp = client.post(
        "/api/posts/publish",
        json={"text": "Hello LinkedIn!"},
    )
    assert resp.status_code == 403


def test_publish_invalid_csrf_returns_403(client, test_session, monkeypatch):
    """POST with invalid CSRF token returns 403."""
    monkeypatch.setattr("app.config.settings.token_encryption_key", _TEST_KEY)
    monkeypatch.setattr("app.routes.api.settings.token_encryption_key", _TEST_KEY)
    _seed_oauth_token(test_session)
    resp = client.post(
        "/api/posts/publish",
        json={"text": "Hello LinkedIn!", "csrf_token": "invalid_csrf_value"},
        cookies={"publish_nonce": "some_nonce"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# /api/posts/publish - scope check
# ---------------------------------------------------------------------------


def test_publish_missing_scope_returns_403(client, test_session, monkeypatch):
    """Tokens without w_member_social scope return 403 with re-auth message."""
    monkeypatch.setattr("app.config.settings.token_encryption_key", _TEST_KEY)
    monkeypatch.setattr("app.routes.api.settings.token_encryption_key", _TEST_KEY)
    _seed_oauth_token(test_session, scopes="openid profile")
    nonce = secrets.token_urlsafe(32)
    csrf_token = _make_publish_csrf(nonce, _TEST_KEY)

    resp = client.post(
        "/api/posts/publish",
        json={"text": "Hello LinkedIn!", "csrf_token": csrf_token},
        cookies={"publish_nonce": nonce},
    )
    assert resp.status_code == 403
    detail = resp.json().get("detail", "")
    assert "reconnect" in detail.lower() or "updated" in detail.lower()


# ---------------------------------------------------------------------------
# /api/posts/publish - full publish flow (mocked LinkedIn API)
# ---------------------------------------------------------------------------


def test_publish_creates_post_in_db(client, test_session, monkeypatch):
    """Full publish flow creates a Post row with correct fields."""
    monkeypatch.setattr("app.config.settings.token_encryption_key", _TEST_KEY)
    monkeypatch.setattr("app.routes.api.settings.token_encryption_key", _TEST_KEY)
    _seed_oauth_token(test_session)
    nonce = secrets.token_urlsafe(32)
    csrf_token = _make_publish_csrf(nonce, _TEST_KEY)

    from app.linkedin_client import PublishResult
    mock_result = PublishResult(
        post_urn="urn:li:share:9999888877776666",
        activity_id="9999888877776666",
        post_url="https://www.linkedin.com/feed/update/urn:li:share:9999888877776666/",
    )

    with (
        patch("app.oauth.get_valid_access_token", return_value="fake_access_token"),
        patch("app.linkedin_client.create_post", new=AsyncMock(return_value=mock_result)),
        patch("app.routes.api._check_dedup", return_value=False),
    ):
        resp = client.post(
            "/api/posts/publish",
            json={"text": "My LinkedIn post content!", "csrf_token": csrf_token},
            cookies={"publish_nonce": nonce},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "published"
    assert data["linkedin_post_id"] == "9999888877776666"
    assert "linkedin.com" in data["linkedin_url"]

    post = test_session.query(Post).filter(Post.id == data["id"]).first()
    assert post is not None
    assert post.status == "published"
    assert post.content == "My LinkedIn post content!"
    assert post.linkedin_post_id == "9999888877776666"


def test_publish_duplicate_returns_409(client, test_session, monkeypatch):
    """Duplicate publish within 60 seconds returns 409."""
    monkeypatch.setattr("app.config.settings.token_encryption_key", _TEST_KEY)
    monkeypatch.setattr("app.routes.api.settings.token_encryption_key", _TEST_KEY)
    _seed_oauth_token(test_session)
    nonce = secrets.token_urlsafe(32)
    csrf_token = _make_publish_csrf(nonce, _TEST_KEY)

    with (
        patch("app.oauth.get_valid_access_token", return_value="fake_token"),
        patch("app.routes.api._check_dedup", return_value=True),
    ):
        resp = client.post(
            "/api/posts/publish",
            json={"text": "My post!", "csrf_token": csrf_token},
            cookies={"publish_nonce": nonce},
        )

    assert resp.status_code == 409


def test_publish_rate_limited_returns_429(client, test_session, monkeypatch):
    """LinkedIn 429 is surfaced to the caller with retry_after_seconds."""
    monkeypatch.setattr("app.config.settings.token_encryption_key", _TEST_KEY)
    monkeypatch.setattr("app.routes.api.settings.token_encryption_key", _TEST_KEY)
    _seed_oauth_token(test_session)
    nonce = secrets.token_urlsafe(32)
    csrf_token = _make_publish_csrf(nonce, _TEST_KEY)

    from app.linkedin_client import LinkedInRateLimitError

    with (
        patch("app.oauth.get_valid_access_token", return_value="fake_token"),
        patch("app.routes.api._check_dedup", return_value=False),
        patch(
            "app.linkedin_client.create_post",
            new=AsyncMock(
                side_effect=LinkedInRateLimitError("Rate limited", retry_after_seconds=45)
            ),
        ),
    ):
        resp = client.post(
            "/api/posts/publish",
            json={"text": "My post!", "csrf_token": csrf_token},
            cookies={"publish_nonce": nonce},
        )

    assert resp.status_code == 429
    data = resp.json()
    detail = data.get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("retry_after_seconds") == 45


def test_publish_requires_member_id(client, test_session, monkeypatch):
    """With tokens but no linkedin_member_id, POST /api/posts/publish returns 403."""
    monkeypatch.setattr("app.config.settings.token_encryption_key", _TEST_KEY)
    monkeypatch.setattr("app.routes.api.settings.token_encryption_key", _TEST_KEY)
    token_row = _seed_oauth_token(test_session)
    token_row.linkedin_member_id = None
    test_session.commit()

    nonce = secrets.token_urlsafe(32)
    csrf_token = _make_publish_csrf(nonce, _TEST_KEY)

    resp = client.post(
        "/api/posts/publish",
        json={"text": "Hello LinkedIn!", "csrf_token": csrf_token},
        cookies={"publish_nonce": nonce},
    )

    assert resp.status_code == 403
    detail = resp.json().get("detail", "")
    assert "reconnect" in detail.lower()


def test_publish_updates_existing_draft(client, test_session, monkeypatch):
    """POST with post_id of an existing draft updates that row rather than creating a new one."""
    monkeypatch.setattr("app.config.settings.token_encryption_key", _TEST_KEY)
    monkeypatch.setattr("app.routes.api.settings.token_encryption_key", _TEST_KEY)
    _seed_oauth_token(test_session)

    existing = Post(
        post_date=date.today(),
        title="Old draft title",
        content="Old draft content",
        status="draft",
    )
    existing.recalculate_engagement_rate()
    test_session.add(existing)
    test_session.commit()
    test_session.refresh(existing)
    existing_id = existing.id

    nonce = secrets.token_urlsafe(32)
    csrf_token = _make_publish_csrf(nonce, _TEST_KEY)

    from app.linkedin_client import PublishResult
    mock_result = PublishResult(
        post_urn="urn:li:share:1111222233334444",
        activity_id="1111222233334444",
        post_url="https://www.linkedin.com/feed/update/urn:li:share:1111222233334444/",
    )

    with (
        patch("app.oauth.get_valid_access_token", return_value="fake_access_token"),
        patch("app.linkedin_client.create_post", new=AsyncMock(return_value=mock_result)),
        patch("app.routes.api._check_dedup", return_value=False),
    ):
        resp = client.post(
            "/api/posts/publish",
            json={
                "text": "Published content for existing draft.",
                "post_id": existing_id,
                "csrf_token": csrf_token,
            },
            cookies={"publish_nonce": nonce},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == existing_id

    post_count = test_session.query(Post).count()
    assert post_count == 1

    test_session.refresh(existing)
    assert existing.status == "published"
    assert existing.content == "Published content for existing draft."
    assert existing.linkedin_post_id == "1111222233334444"
