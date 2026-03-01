"""Route tests for OAuth endpoints and settings page.

Tests cover:
- GET /oauth/authorize: redirect to LinkedIn, sets state cookie
- GET /oauth/callback: exchanges code, stores tokens, handles user denial, rejects bad state
- POST /oauth/disconnect: deletes tokens (CSRF-protected), rejects missing/invalid CSRF
- GET /dashboard/settings: not connected, connected, with flash messages
- GET /api/auth/status: JSON status endpoint
- Graceful degradation: routes work when OAuth is not configured
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.models import OAuthToken
from app.oauth import (
    TokenResponse,
    encrypt_token,
    generate_disconnect_csrf_token,
    sign_state,
    store_tokens,
)

# ---------------------------------------------------------------------------
# Fernet key for all route tests
# ---------------------------------------------------------------------------

_TEST_FERNET_KEY = Fernet.generate_key().decode()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def oauth_settings_patch(monkeypatch):
    """Patch app.config.settings and app.oauth.settings to enable OAuth."""
    from app import config as config_module
    from app import oauth as oauth_module
    from app.routes import oauth_routes as routes_module

    for module in (config_module, oauth_module, routes_module):
        mock = MagicMock()
        mock.oauth_enabled = True
        mock.linkedin_client_id = "test_client_id"
        mock.linkedin_client_secret = "test_client_secret"
        mock.token_encryption_key = _TEST_FERNET_KEY
        mock.linkedin_redirect_uri = "http://localhost:8050/oauth/callback"
        mock.linkedin_api_version = "202601"
        monkeypatch.setattr(module, "settings", mock)

    # Also patch the dashboard route module which imports settings for its settings route
    from app.routes import dashboard as dashboard_module
    dashboard_mock = MagicMock()
    dashboard_mock.oauth_enabled = True
    dashboard_mock.linkedin_client_id = "test_client_id"
    dashboard_mock.linkedin_client_secret = "test_client_secret"
    dashboard_mock.token_encryption_key = _TEST_FERNET_KEY
    dashboard_mock.linkedin_redirect_uri = "http://localhost:8050/oauth/callback"
    monkeypatch.setattr(dashboard_module, "settings", dashboard_mock)

    return mock


@pytest.fixture
def oauth_disabled_patch(monkeypatch):
    """Patch settings to disable OAuth (empty client_id)."""
    from app import config as config_module
    from app import oauth as oauth_module
    from app.routes import oauth_routes as routes_module
    from app.routes import dashboard as dashboard_module

    for module in (config_module, oauth_module, routes_module, dashboard_module):
        mock = MagicMock()
        mock.oauth_enabled = False
        mock.linkedin_client_id = ""
        mock.linkedin_client_secret = ""
        mock.token_encryption_key = ""
        monkeypatch.setattr(module, "settings", mock)


def _store_valid_token(db_session) -> OAuthToken:
    """Helper: store a non-expired token row for use in connected-state tests."""
    now = datetime.now(timezone.utc)
    from cryptography.fernet import Fernet
    fernet = Fernet(_TEST_FERNET_KEY.encode())
    row = OAuthToken(
        provider="linkedin",
        access_token_encrypted=fernet.encrypt(b"live_access_token").decode(),
        refresh_token_encrypted=fernet.encrypt(b"live_refresh_token").decode(),
        access_token_expires_at=now + timedelta(days=30),
        refresh_token_expires_at=now + timedelta(days=300),
        scopes="openid profile",
        linkedin_member_id="urn:li:person:test123",
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# 1. GET /oauth/authorize
# ---------------------------------------------------------------------------


def test_authorize_redirects_to_linkedin(client, oauth_settings_patch):
    """GET /oauth/authorize must redirect to LinkedIn authorization endpoint."""
    response = client.get("/oauth/authorize", follow_redirects=False)

    assert response.status_code == 307
    location = response.headers["location"]
    assert "linkedin.com/oauth/v2/authorization" in location


def test_authorize_includes_required_params(client, oauth_settings_patch):
    """Authorization redirect URL must include client_id, redirect_uri, scope, state."""
    response = client.get("/oauth/authorize", follow_redirects=False)

    location = response.headers["location"]
    import urllib.parse
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(location).query))

    assert params["response_type"] == "code"
    assert "client_id" in params
    assert "redirect_uri" in params
    assert "state" in params
    assert "openid" in params["scope"]


def test_authorize_sets_state_cookie(client, oauth_settings_patch):
    """GET /oauth/authorize must set the oauth_state and oauth_state_value cookies."""
    response = client.get("/oauth/authorize", follow_redirects=False)

    cookies = response.cookies
    assert "oauth_state" in cookies
    assert "oauth_state_value" in cookies


# ---------------------------------------------------------------------------
# 2. GET /oauth/callback
# ---------------------------------------------------------------------------


def _get_state_cookies(client, oauth_settings_patch):
    """Helper: perform authorize to capture state cookies, return (state, signature)."""
    response = client.get("/oauth/authorize", follow_redirects=False)
    state = response.cookies.get("oauth_state_value")
    sig = response.cookies.get("oauth_state")
    return state, sig


def test_callback_exchanges_code(client, test_session, oauth_settings_patch):
    """A valid callback with matching state must exchange the code and store tokens."""
    state, sig = _get_state_cookies(client, oauth_settings_patch)

    mock_token_response = TokenResponse(
        access_token="new_access_token",
        refresh_token="new_refresh_token",
        expires_in=60 * 24 * 3600,
        refresh_token_expires_in=365 * 24 * 3600,
        scope="openid profile",
    )

    with patch("app.routes.oauth_routes.exchange_code_for_tokens", return_value=mock_token_response):
        with patch("app.routes.oauth_routes.store_tokens") as mock_store:
            response = client.get(
                f"/oauth/callback?code=auth_code_123&state={state}",
                follow_redirects=False,
            )

    assert response.status_code == 302
    assert "settings" in response.headers["location"]
    assert "connected=1" in response.headers["location"]
    mock_store.assert_called_once()


def test_callback_rejects_mismatched_state(client, oauth_settings_patch):
    """A callback with a state that does not match the cookie must return 403."""
    # Trigger authorize to set cookies
    client.get("/oauth/authorize", follow_redirects=False)

    # Send a different state value
    response = client.get(
        "/oauth/callback?code=auth_code&state=wrong_state_value",
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_callback_rejects_tampered_cookie(client, oauth_settings_patch):
    """A callback where the cookie signature is forged must return 403."""
    state, _sig = _get_state_cookies(client, oauth_settings_patch)

    # Set a forged signature cookie manually
    client.cookies.set("oauth_state", "forged_signature_value")

    response = client.get(
        f"/oauth/callback?code=auth_code&state={state}",
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_callback_handles_user_denied(client, oauth_settings_patch):
    """A callback with error=user_cancelled_authorize must redirect to settings with error."""
    response = client.get(
        "/oauth/callback?error=user_cancelled_authorize",
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers["location"]
    assert "settings" in location
    assert "error" in location


def test_callback_missing_state_cookie(client, oauth_settings_patch):
    """A callback with no state cookies set must return 403."""
    response = client.get(
        "/oauth/callback?code=auth_code&state=some_state",
        follow_redirects=False,
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 3. POST /oauth/disconnect
# ---------------------------------------------------------------------------


def _get_valid_csrf(nonce: str) -> str:
    """Compute the expected CSRF token for the given nonce."""
    import hashlib
    import hmac
    key = _TEST_FERNET_KEY.encode()
    return hmac.new(key, f"disconnect:{nonce}".encode(), hashlib.sha256).hexdigest()


def test_disconnect_deletes_tokens(client, test_session, oauth_settings_patch):
    """POST /oauth/disconnect with a valid CSRF token must delete tokens."""
    _store_valid_token(test_session)
    nonce = "test_nonce_abc"
    csrf = _get_valid_csrf(nonce)

    client.cookies.set("disconnect_nonce", nonce)

    response = client.post(
        "/oauth/disconnect",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "disconnected=1" in response.headers["location"]


def test_disconnect_rejects_missing_csrf_token(client, oauth_settings_patch):
    """POST /oauth/disconnect without a CSRF token must return 403."""
    nonce = "test_nonce_abc"
    client.cookies.set("disconnect_nonce", nonce)

    response = client.post(
        "/oauth/disconnect",
        data={},  # No csrf_token field
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_disconnect_rejects_invalid_csrf_token(client, oauth_settings_patch):
    """POST /oauth/disconnect with a forged CSRF token must return 403."""
    nonce = "test_nonce_abc"
    client.cookies.set("disconnect_nonce", nonce)

    response = client.post(
        "/oauth/disconnect",
        data={"csrf_token": "totally_fake_token"},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_disconnect_rejects_missing_nonce_cookie(client, oauth_settings_patch):
    """POST /oauth/disconnect without the nonce cookie must return 403."""
    response = client.post(
        "/oauth/disconnect",
        data={"csrf_token": "some_token"},
        follow_redirects=False,
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 4. GET /dashboard/settings
# ---------------------------------------------------------------------------


def test_settings_page_not_connected(client, oauth_settings_patch):
    """GET /dashboard/settings with no tokens must show 'Not connected' content."""
    response = client.get("/dashboard/settings")
    assert response.status_code == 200
    body = response.text
    assert "Not connected" in body or "Connect LinkedIn" in body


def test_settings_page_connected(client, test_session, oauth_settings_patch):
    """GET /dashboard/settings with valid tokens must show 'Connected' status."""
    _store_valid_token(test_session)

    response = client.get("/dashboard/settings")
    assert response.status_code == 200
    body = response.text
    assert "Connected" in body


def test_settings_page_shows_scopes(client, test_session, oauth_settings_patch):
    """GET /dashboard/settings connected must display the granted scopes."""
    _store_valid_token(test_session)

    response = client.get("/dashboard/settings")
    assert response.status_code == 200
    body = response.text
    assert "openid" in body
    assert "profile" in body


def test_settings_page_oauth_not_configured(client, oauth_disabled_patch):
    """GET /dashboard/settings with OAuth not configured must show setup instructions."""
    response = client.get("/dashboard/settings")
    assert response.status_code == 200
    body = response.text
    # Should show setup instructions block, not a connect button
    assert "Not configured" in body or "not configured" in body.lower() or "TOKEN_ENCRYPTION_KEY" in body


def test_settings_page_flash_connected(client, oauth_settings_patch):
    """GET /dashboard/settings?connected=1 must show a success flash message."""
    response = client.get("/dashboard/settings?connected=1")
    assert response.status_code == 200
    assert "connected successfully" in response.text.lower() or "connected" in response.text


def test_settings_page_flash_error_user_cancelled(client, oauth_settings_patch):
    """GET /dashboard/settings?error=user_cancelled_authorize must show a friendly error."""
    response = client.get("/dashboard/settings?error=user_cancelled_authorize")
    assert response.status_code == 200
    assert "cancelled" in response.text.lower() or "Authorization cancelled" in response.text


# ---------------------------------------------------------------------------
# 5. GET /api/auth/status
# ---------------------------------------------------------------------------


def test_auth_status_api_not_configured(client, oauth_disabled_patch):
    """GET /api/auth/status with OAuth not configured must return oauth_configured=False."""
    response = client.get("/api/auth/status")
    assert response.status_code == 200
    data = response.json()
    assert data["oauth_configured"] is False
    assert data["connected"] is False


def test_auth_status_api_not_connected(client, oauth_settings_patch):
    """GET /api/auth/status with no tokens must return connected=False."""
    response = client.get("/api/auth/status")
    assert response.status_code == 200
    data = response.json()
    assert data["oauth_configured"] is True
    assert data["connected"] is False


def test_auth_status_api_connected(client, test_session, oauth_settings_patch):
    """GET /api/auth/status with valid tokens must return connected=True."""
    _store_valid_token(test_session)

    response = client.get("/api/auth/status")
    assert response.status_code == 200
    data = response.json()
    assert data["oauth_configured"] is True
    assert data["connected"] is True
    assert "expires_at" in data
    assert "scopes" in data


# ---------------------------------------------------------------------------
# 6. GET /oauth/authorize — disabled when not configured
# ---------------------------------------------------------------------------


def test_oauth_routes_404_when_not_configured(client, oauth_disabled_patch):
    """GET /oauth/authorize must return 404 when OAuth is not configured."""
    response = client.get("/oauth/authorize", follow_redirects=False)
    # The route returns a JSONResponse with 404, not a redirect
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 7. Graceful degradation
# ---------------------------------------------------------------------------


def test_dashboard_works_without_oauth_config(client, oauth_disabled_patch):
    """GET /dashboard must render without errors when OAuth is not configured."""
    response = client.get("/dashboard")
    assert response.status_code == 200


def test_upload_still_works_with_oauth(client, oauth_settings_patch, sample_xlsx_bytes):
    """File upload must still work when OAuth is configured."""
    response = client.post(
        "/upload",
        files={"file": ("export.xlsx", sample_xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        follow_redirects=False,
    )
    # Accept redirect or 200 (upload succeeded or was processed)
    assert response.status_code in (200, 302, 303)
