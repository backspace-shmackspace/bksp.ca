"""Unit tests for app/oauth.py.

Tests cover:
- Authorization URL construction
- Fernet encrypt/decrypt round-trip and error handling
- HMAC state signing and verification
- CSRF token generation and verification for the disconnect form
- Token storage (create and upsert)
- Auth status queries (connected, not connected, needs_reauth)
- get_valid_access_token: not expired, expired with successful refresh, refresh token expired
- Token revocation
- Exception sanitization (no client_secret in re-raised exceptions)
- Redirect URI validation at startup
"""

import hashlib
import hmac
import urllib.parse
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.models import Base, OAuthToken
from app.oauth import (
    AuthStatus,
    OAuthTokenExchangeError,
    TokenResponse,
    build_authorization_url,
    decrypt_token,
    encrypt_token,
    generate_disconnect_csrf_token,
    generate_state,
    get_auth_status,
    get_valid_access_token,
    revoke_tokens,
    sign_state,
    store_tokens,
    verify_disconnect_csrf_token,
    verify_state_signature,
)

# ---------------------------------------------------------------------------
# Test-scoped Fernet key and in-memory DB fixtures
# ---------------------------------------------------------------------------

_TEST_FERNET_KEY = Fernet.generate_key().decode()
_ANOTHER_FERNET_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    """Patch app.oauth.settings with test-safe OAuth values for every test."""
    from app import oauth as oauth_module
    from app import config as config_module

    mock_settings = MagicMock()
    mock_settings.token_encryption_key = _TEST_FERNET_KEY
    mock_settings.linkedin_client_id = "test_client_id"
    mock_settings.linkedin_client_secret = "test_client_secret"
    mock_settings.linkedin_redirect_uri = "http://localhost:8050/oauth/callback"
    mock_settings.linkedin_api_version = "202601"
    mock_settings.oauth_enabled = True

    monkeypatch.setattr(oauth_module, "settings", mock_settings)
    return mock_settings


@pytest.fixture
def db_session():
    """Create a fresh in-memory SQLite session for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _make_token_response(
    access_token: str = "access_token_value",
    refresh_token: str = "refresh_token_value",
    expires_in: int = 60 * 24 * 3600,
    refresh_token_expires_in: int = 365 * 24 * 3600,
    scope: str = "openid profile",
) -> TokenResponse:
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        refresh_token_expires_in=refresh_token_expires_in,
        scope=scope,
    )


def _store_expired_tokens(db, *, access_expired: bool = True, refresh_expired: bool = False) -> OAuthToken:
    """Helper: store tokens with controlled expiry for refresh tests."""
    now = datetime.now(timezone.utc)
    access_delta = timedelta(hours=-1) if access_expired else timedelta(days=30)
    refresh_delta = timedelta(hours=-1) if refresh_expired else timedelta(days=300)

    from app.oauth import encrypt_token as _enc
    row = OAuthToken(
        provider="linkedin",
        access_token_encrypted=_enc("live_access_token"),
        refresh_token_encrypted=_enc("live_refresh_token"),
        access_token_expires_at=now + access_delta,
        refresh_token_expires_at=now + refresh_delta,
        scopes="openid profile",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# 1. build_authorization_url
# ---------------------------------------------------------------------------


def test_build_authorization_url():
    """Authorization URL must include required OAuth parameters."""
    state = "test_state_value"
    url = build_authorization_url(state)

    parsed = urllib.parse.urlparse(url)
    assert parsed.scheme == "https"
    assert "linkedin.com" in parsed.netloc

    params = dict(urllib.parse.parse_qsl(parsed.query))
    assert params["response_type"] == "code"
    assert params["client_id"] == "test_client_id"
    assert params["redirect_uri"] == "http://localhost:8050/oauth/callback"
    assert params["state"] == state
    assert "openid" in params["scope"]
    assert "profile" in params["scope"]


def test_build_authorization_url_uses_configured_redirect_uri(monkeypatch):
    """build_authorization_url must use the redirect URI from settings."""
    from app import oauth as oauth_module

    mock_settings = MagicMock()
    mock_settings.token_encryption_key = _TEST_FERNET_KEY
    mock_settings.linkedin_client_id = "cid"
    mock_settings.linkedin_redirect_uri = "https://example.com/oauth/callback"
    monkeypatch.setattr(oauth_module, "settings", mock_settings)

    url = build_authorization_url("some_state")
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert params["redirect_uri"] == "https://example.com/oauth/callback"


# ---------------------------------------------------------------------------
# 2. Fernet encrypt / decrypt
# ---------------------------------------------------------------------------


def test_encrypt_decrypt_token():
    """Encrypt then decrypt must return the original plaintext."""
    original = "super_secret_access_token_value"
    ciphertext = encrypt_token(original)
    assert ciphertext != original
    assert decrypt_token(ciphertext) == original


def test_encrypt_returns_string():
    """encrypt_token must return a str, not bytes."""
    result = encrypt_token("token")
    assert isinstance(result, str)


def test_fernet_key_validated_at_startup():
    """A malformed TOKEN_ENCRYPTION_KEY must cause Settings instantiation to fail."""
    from pydantic import ValidationError
    from app.config import Settings

    with pytest.raises((ValueError, ValidationError)):
        Settings(
            token_encryption_key="not-a-valid-fernet-key",
            _env_file=None,
        )


def test_fernet_key_empty_disables_oauth():
    """An empty TOKEN_ENCRYPTION_KEY is allowed; oauth_enabled returns False."""
    from app.config import Settings

    s = Settings(
        linkedin_client_id="",
        linkedin_client_secret="",
        token_encryption_key="",
        _env_file=None,
    )
    assert s.oauth_enabled is False


def test_decrypt_with_wrong_key_returns_none(monkeypatch):
    """Decrypting with a different key must return None, not raise."""
    from app import oauth as oauth_module

    # Encrypt with key A
    enc = Fernet(_TEST_FERNET_KEY.encode()).encrypt(b"secret_token").decode()

    # Patch settings to use a different key for decryption
    mock_settings = MagicMock()
    mock_settings.token_encryption_key = _ANOTHER_FERNET_KEY
    monkeypatch.setattr(oauth_module, "settings", mock_settings)

    result = decrypt_token(enc)
    assert result is None


# ---------------------------------------------------------------------------
# 3. HMAC state signing
# ---------------------------------------------------------------------------


def test_sign_and_verify_state():
    """sign_state + verify_state_signature must return True for a valid pair."""
    state = generate_state()
    sig = sign_state(state)
    assert verify_state_signature(state, sig) is True


def test_tampered_state_cookie_rejected():
    """A tampered signature must fail verification."""
    state = generate_state()
    sig = sign_state(state)
    tampered_sig = sig[:-4] + "xxxx"
    assert verify_state_signature(state, tampered_sig) is False


def test_different_state_same_signature_rejected():
    """Verifying a different state value against an existing signature must fail."""
    state = generate_state()
    sig = sign_state(state)
    other_state = generate_state()
    assert verify_state_signature(other_state, sig) is False


# ---------------------------------------------------------------------------
# 4. CSRF token for disconnect form
# ---------------------------------------------------------------------------


def test_generate_and_verify_disconnect_csrf_token():
    """generate_disconnect_csrf_token + verify_disconnect_csrf_token must return True."""
    nonce = "test_nonce_value"
    token = generate_disconnect_csrf_token(nonce)
    assert verify_disconnect_csrf_token(nonce, token) is True


def test_tampered_csrf_token_rejected():
    """A tampered disconnect CSRF token must fail verification."""
    nonce = "test_nonce_value"
    token = generate_disconnect_csrf_token(nonce)
    bad_token = token[:-4] + "zzzz"
    assert verify_disconnect_csrf_token(nonce, bad_token) is False


def test_wrong_nonce_csrf_rejected():
    """A CSRF token generated with a different nonce must fail verification."""
    token = generate_disconnect_csrf_token("nonce_a")
    assert verify_disconnect_csrf_token("nonce_b", token) is False


# ---------------------------------------------------------------------------
# 5. store_tokens
# ---------------------------------------------------------------------------


def test_store_tokens_creates_row(db_session):
    """store_tokens must create a row with encrypted values."""
    tr = _make_token_response()
    row = store_tokens(db_session, tr, member_id="urn:li:person:abc123")

    assert row.id is not None
    assert row.provider == "linkedin"
    assert row.access_token_encrypted != "access_token_value"
    assert row.refresh_token_encrypted != "refresh_token_value"
    assert row.scopes == "openid profile"
    assert row.linkedin_member_id == "urn:li:person:abc123"


def test_store_tokens_upserts_on_reauth(db_session):
    """Calling store_tokens twice must update the existing row, not insert a second."""
    tr1 = _make_token_response(access_token="first_token")
    store_tokens(db_session, tr1)

    tr2 = _make_token_response(access_token="second_token")
    store_tokens(db_session, tr2)

    rows = db_session.query(OAuthToken).filter(OAuthToken.provider == "linkedin").all()
    assert len(rows) == 1
    assert decrypt_token(rows[0].access_token_encrypted) == "second_token"


def test_store_tokens_access_expiry_set(db_session):
    """store_tokens must set access_token_expires_at from expires_in."""
    tr = _make_token_response(expires_in=3600)
    before = datetime.now(timezone.utc)
    row = store_tokens(db_session, tr)
    after = datetime.now(timezone.utc)

    expires_at = row.access_token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    assert before + timedelta(seconds=3590) <= expires_at <= after + timedelta(seconds=3610)


# ---------------------------------------------------------------------------
# 6. get_auth_status
# ---------------------------------------------------------------------------


def test_get_auth_status_not_connected(db_session):
    """With no token row, get_auth_status must return connected=False."""
    status = get_auth_status(db_session)
    assert status.connected is False
    assert status.expires_at is None


def test_get_auth_status_connected(db_session):
    """With valid tokens, get_auth_status must return connected=True with metadata."""
    tr = _make_token_response(scope="openid profile")
    store_tokens(db_session, tr, member_id="urn:li:person:xyz")

    status = get_auth_status(db_session)

    assert status.connected is True
    assert "openid" in status.scopes
    assert "profile" in status.scopes
    assert status.expires_at is not None
    assert status.member_id == "urn:li:person:xyz"
    assert status.needs_reauth is False


def test_get_auth_status_needs_reauth(db_session):
    """With an expired refresh token, get_auth_status must return needs_reauth=True."""
    _store_expired_tokens(db_session, access_expired=True, refresh_expired=True)
    status = get_auth_status(db_session)
    assert status.needs_reauth is True


def test_get_auth_status_wrong_key_returns_not_connected(db_session, monkeypatch):
    """If token decryption fails (key rotation), get_auth_status returns connected=False."""
    from app import oauth as oauth_module

    # Store tokens with the current key.
    tr = _make_token_response()
    store_tokens(db_session, tr)

    # Rotate to a different key.
    mock_settings = MagicMock()
    mock_settings.token_encryption_key = _ANOTHER_FERNET_KEY
    monkeypatch.setattr(oauth_module, "settings", mock_settings)

    status = get_auth_status(db_session)
    assert status.connected is False
    assert status.needs_reauth is True


# ---------------------------------------------------------------------------
# 7. get_valid_access_token
# ---------------------------------------------------------------------------


def test_get_valid_access_token_not_expired(db_session):
    """With a token that expires in 30 days, return the decrypted token directly."""
    tr = _make_token_response(access_token="fresh_access_token", expires_in=30 * 24 * 3600)
    store_tokens(db_session, tr)

    result = get_valid_access_token(db_session)
    assert result == "fresh_access_token"


def test_get_valid_access_token_no_row(db_session):
    """With no token row, get_valid_access_token must return None."""
    result = get_valid_access_token(db_session)
    assert result is None


def test_get_valid_access_token_expired_refresh_succeeds(db_session):
    """With an expired access token and valid refresh token, auto-refresh and return new token."""
    _store_expired_tokens(db_session, access_expired=True, refresh_expired=False)

    new_tr = _make_token_response(
        access_token="refreshed_access_token",
        expires_in=60 * 24 * 3600,
    )

    with patch("app.oauth.refresh_access_token", return_value=new_tr) as mock_refresh:
        result = get_valid_access_token(db_session)

    mock_refresh.assert_called_once()
    assert result == "refreshed_access_token"


def test_get_valid_access_token_refresh_token_expired(db_session):
    """With both tokens expired, return None and do not attempt refresh."""
    _store_expired_tokens(db_session, access_expired=True, refresh_expired=True)

    with patch("app.oauth.refresh_access_token") as mock_refresh:
        result = get_valid_access_token(db_session)

    mock_refresh.assert_not_called()
    assert result is None


def test_get_valid_access_token_refresh_call_fails(db_session):
    """If the refresh HTTP call fails, return None gracefully."""
    _store_expired_tokens(db_session, access_expired=True, refresh_expired=False)

    with patch("app.oauth.refresh_access_token", side_effect=OAuthTokenExchangeError("LinkedIn returned status 400")):
        result = get_valid_access_token(db_session)

    assert result is None


# ---------------------------------------------------------------------------
# 8. revoke_tokens
# ---------------------------------------------------------------------------


def test_revoke_tokens_deletes_row(db_session):
    """revoke_tokens must delete the oauth_tokens row."""
    tr = _make_token_response()
    store_tokens(db_session, tr)

    assert db_session.query(OAuthToken).count() == 1

    revoke_tokens(db_session)

    assert db_session.query(OAuthToken).count() == 0


def test_revoke_tokens_no_row_no_error(db_session):
    """revoke_tokens with no row must complete without raising."""
    revoke_tokens(db_session)  # Should not raise


# ---------------------------------------------------------------------------
# 9. Exception sanitization
# ---------------------------------------------------------------------------


def test_exception_sanitization_no_secret_in_error():
    """OAuthTokenExchangeError message must not contain client_secret."""
    import httpx

    error = OAuthTokenExchangeError("LinkedIn returned status 400")
    assert "test_client_secret" not in str(error)
    assert "client_secret" not in str(error)


def test_exchange_code_sanitizes_http_status_error(monkeypatch):
    """exchange_code_for_tokens must raise OAuthTokenExchangeError with only a status code message."""
    import httpx
    from app.oauth import exchange_code_for_tokens

    def mock_post(*args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        raise httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=mock_resp)

    monkeypatch.setattr(httpx, "post", mock_post)

    with pytest.raises(OAuthTokenExchangeError) as exc_info:
        exchange_code_for_tokens("bad_code")

    error_msg = str(exc_info.value)
    assert "401" in error_msg
    assert "test_client_secret" not in error_msg
    assert "client_secret" not in error_msg


def test_exchange_code_sanitizes_network_error(monkeypatch):
    """exchange_code_for_tokens must raise OAuthTokenExchangeError on network errors."""
    import httpx
    from app.oauth import exchange_code_for_tokens

    def mock_post(*args, **kwargs):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx, "post", mock_post)

    with pytest.raises(OAuthTokenExchangeError) as exc_info:
        exchange_code_for_tokens("code")

    error_msg = str(exc_info.value)
    assert "network error" in error_msg.lower()
    assert "test_client_secret" not in error_msg


# ---------------------------------------------------------------------------
# 10. Redirect URI validation
# ---------------------------------------------------------------------------


def test_redirect_uri_path_validation_correct():
    """A valid /oauth/callback path must not raise."""
    from app.config import Settings, validate_redirect_uri

    s = Settings(
        linkedin_client_id="cid",
        linkedin_client_secret="secret",
        token_encryption_key=_TEST_FERNET_KEY,
        linkedin_redirect_uri="http://localhost:8050/oauth/callback",
        _env_file=None,
    )
    validate_redirect_uri(s)  # Must not raise


def test_redirect_uri_path_validation_wrong_path():
    """A redirect URI with a non-/oauth/callback path must raise ValueError."""
    from app.config import Settings, validate_redirect_uri

    s = Settings(
        linkedin_client_id="cid",
        linkedin_client_secret="secret",
        token_encryption_key=_TEST_FERNET_KEY,
        linkedin_redirect_uri="http://localhost:8050/wrong/path",
        _env_file=None,
    )
    with pytest.raises(ValueError, match="path must be '/oauth/callback'"):
        validate_redirect_uri(s)
