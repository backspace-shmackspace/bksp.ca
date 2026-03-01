"""LinkedIn OAuth 2.0 flow logic.

Handles authorization URL construction, token exchange, token refresh,
Fernet encryption/decryption, HMAC state signing, token storage, and
auth status queries. All sensitive exceptions are sanitized before
propagation to prevent client_secret leakage.
"""

import hashlib
import hmac
import logging
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.config import settings
from app.models import OAuthToken

logger = logging.getLogger(__name__)

# In-process lock to prevent concurrent token refresh attempts.
_refresh_lock = threading.Lock()

# LinkedIn OAuth endpoints
_AUTHORIZATION_URL = "https://www.linkedin.com/oauth/v2/authorization"
_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"

# Scopes: openid and profile come with "Share on LinkedIn" (auto-granted).
# r_member_postAnalytics and community management scopes will be added in the
# data sync plan after Community Management API access is confirmed.
_SCOPES = "openid profile"

# Token lifetime constants (from LinkedIn documentation)
_ACCESS_TOKEN_LIFETIME_SECONDS = 60 * 24 * 3600  # 60 days
_REFRESH_TOKEN_LIFETIME_SECONDS = 365 * 24 * 3600  # 365 days

# Refresh buffer: refresh the access token if it expires within this window.
_REFRESH_BUFFER_SECONDS = 300  # 5 minutes


class OAuthTokenExchangeError(Exception):
    """Raised when the LinkedIn token exchange or refresh call fails.

    The message contains only sanitized information (HTTP status code or
    'network error'). It never contains request body, headers, or URLs that
    might include client_secret.
    """


@dataclass
class TokenResponse:
    """Parsed response from LinkedIn's token endpoint."""

    access_token: str
    refresh_token: str
    expires_in: int  # seconds
    refresh_token_expires_in: int  # seconds
    scope: str
    linkedin_member_id: str | None = None


@dataclass
class AuthStatus:
    """Current OAuth connection status."""

    connected: bool
    expires_at: datetime | None = None
    refresh_expires_at: datetime | None = None
    scopes: list[str] = field(default_factory=list)
    needs_reauth: bool = False
    member_id: str | None = None


# ---------------------------------------------------------------------------
# Encryption / Decryption
# ---------------------------------------------------------------------------


def _get_fernet() -> Fernet:
    """Return a Fernet instance using the configured encryption key."""
    return Fernet(settings.token_encryption_key.encode())


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token string with Fernet. Returns a base64-encoded ciphertext."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str | None:
    """Decrypt a Fernet-encrypted token string.

    Returns the plaintext string, or None if the ciphertext is invalid
    (e.g. after key rotation). The caller should treat None as 'not connected'
    and prompt re-authorization.
    """
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.warning("Token decryption failed (InvalidToken). Key may have been rotated.")
        return None


# ---------------------------------------------------------------------------
# HMAC State Signing
# ---------------------------------------------------------------------------


def generate_state() -> str:
    """Generate a cryptographically random state token."""
    return secrets.token_urlsafe(32)


def sign_state(state: str) -> str:
    """HMAC-sign the state value using TOKEN_ENCRYPTION_KEY.

    Returns the hex-encoded HMAC-SHA256 signature. This reuses the existing
    Fernet key material for signing, avoiding a new env var.
    """
    key = settings.token_encryption_key.encode()
    return hmac.new(key, state.encode(), hashlib.sha256).hexdigest()


def verify_state_signature(state: str, signature: str) -> bool:
    """Verify an HMAC-SHA256 signature for a state value.

    Uses hmac.compare_digest to prevent timing attacks.
    """
    expected = sign_state(state)
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# CSRF Token for Disconnect Form
# ---------------------------------------------------------------------------


def generate_disconnect_csrf_token(nonce: str) -> str:
    """Generate a CSRF token for the disconnect form.

    The token is an HMAC-SHA256 of 'disconnect:<nonce>' keyed with
    TOKEN_ENCRYPTION_KEY. The nonce is stored in a cookie set when the
    settings page is rendered.
    """
    key = settings.token_encryption_key.encode()
    message = f"disconnect:{nonce}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def verify_disconnect_csrf_token(nonce: str, token: str) -> bool:
    """Verify the disconnect form CSRF token using hmac.compare_digest."""
    expected = generate_disconnect_csrf_token(nonce)
    return hmac.compare_digest(expected, token)


# ---------------------------------------------------------------------------
# Authorization URL
# ---------------------------------------------------------------------------


def build_authorization_url(state: str) -> str:
    """Construct the LinkedIn authorization URL.

    Args:
        state: A random state value for CSRF protection.

    Returns:
        The full LinkedIn authorization URL to redirect the user to.
    """
    import urllib.parse

    params = {
        "response_type": "code",
        "client_id": settings.linkedin_client_id,
        "redirect_uri": settings.linkedin_redirect_uri,
        "scope": _SCOPES,
        "state": state,
    }
    return f"{_AUTHORIZATION_URL}?{urllib.parse.urlencode(params)}"


# ---------------------------------------------------------------------------
# Token Exchange and Refresh
# ---------------------------------------------------------------------------


def exchange_code_for_tokens(code: str) -> TokenResponse:
    """Exchange an authorization code for access and refresh tokens.

    POSTs to LinkedIn's token endpoint. All exceptions are caught and
    re-raised as OAuthTokenExchangeError with sanitized messages to prevent
    client_secret from appearing in logs or stack traces.

    Args:
        code: The authorization code from LinkedIn's callback.

    Returns:
        A TokenResponse with access_token, refresh_token, and metadata.

    Raises:
        OAuthTokenExchangeError: On any HTTP or network error.
    """
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.linkedin_redirect_uri,
        "client_id": settings.linkedin_client_id,
        "client_secret": settings.linkedin_client_secret,
    }
    try:
        response = httpx.post(_TOKEN_URL, data=payload, timeout=httpx.Timeout(10.0))
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error("Token exchange failed with status %d", e.response.status_code)
        raise OAuthTokenExchangeError(
            f"LinkedIn returned status {e.response.status_code}"
        ) from None
    except httpx.HTTPError:
        logger.error("Token exchange failed: network error")
        raise OAuthTokenExchangeError("Network error during token exchange") from None

    data = response.json()
    return TokenResponse(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", ""),
        expires_in=data.get("expires_in", _ACCESS_TOKEN_LIFETIME_SECONDS),
        refresh_token_expires_in=data.get(
            "refresh_token_expires_in", _REFRESH_TOKEN_LIFETIME_SECONDS
        ),
        scope=data.get("scope", _SCOPES),
    )


def refresh_access_token(refresh_token: str) -> TokenResponse:
    """Exchange a refresh token for a new access token.

    Same exception sanitization as exchange_code_for_tokens.

    Args:
        refresh_token: The plaintext refresh token.

    Returns:
        A TokenResponse with updated access_token and metadata.

    Raises:
        OAuthTokenExchangeError: On any HTTP or network error.
    """
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.linkedin_client_id,
        "client_secret": settings.linkedin_client_secret,
    }
    try:
        response = httpx.post(_TOKEN_URL, data=payload, timeout=httpx.Timeout(10.0))
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error("Token refresh failed with status %d", e.response.status_code)
        raise OAuthTokenExchangeError(
            f"LinkedIn returned status {e.response.status_code}"
        ) from None
    except httpx.HTTPError:
        logger.error("Token refresh failed: network error")
        raise OAuthTokenExchangeError("Network error during token refresh") from None

    data = response.json()
    return TokenResponse(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", refresh_token),
        expires_in=data.get("expires_in", _ACCESS_TOKEN_LIFETIME_SECONDS),
        refresh_token_expires_in=data.get(
            "refresh_token_expires_in", _REFRESH_TOKEN_LIFETIME_SECONDS
        ),
        scope=data.get("scope", _SCOPES),
    )


# ---------------------------------------------------------------------------
# Token Storage
# ---------------------------------------------------------------------------


def store_tokens(
    db: Session,
    token_response: TokenResponse,
    member_id: str | None = None,
) -> OAuthToken:
    """Encrypt and upsert tokens in the oauth_tokens table.

    Single-user design: there is at most one row with provider='linkedin'.
    On re-authorization, the existing row is updated in place.

    Args:
        db: SQLAlchemy session.
        token_response: Parsed token response from LinkedIn.
        member_id: Optional LinkedIn member URN from /userinfo.

    Returns:
        The OAuthToken row (created or updated).
    """
    now = datetime.now(timezone.utc)
    access_expires_at = now + timedelta(seconds=token_response.expires_in)
    refresh_expires_at = now + timedelta(seconds=token_response.refresh_token_expires_in)

    encrypted_access = encrypt_token(token_response.access_token)
    encrypted_refresh = encrypt_token(token_response.refresh_token)

    existing = db.query(OAuthToken).filter(OAuthToken.provider == "linkedin").first()
    if existing:
        existing.access_token_encrypted = encrypted_access
        existing.refresh_token_encrypted = encrypted_refresh
        existing.access_token_expires_at = access_expires_at
        existing.refresh_token_expires_at = refresh_expires_at
        existing.scopes = token_response.scope
        if member_id is not None:
            existing.linkedin_member_id = member_id
        db.commit()
        db.refresh(existing)
        return existing
    else:
        row = OAuthToken(
            provider="linkedin",
            access_token_encrypted=encrypted_access,
            refresh_token_encrypted=encrypted_refresh,
            access_token_expires_at=access_expires_at,
            refresh_token_expires_at=refresh_expires_at,
            scopes=token_response.scope,
            linkedin_member_id=member_id,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row


# ---------------------------------------------------------------------------
# Token Retrieval and Refresh
# ---------------------------------------------------------------------------


def get_valid_access_token(db: Session) -> str | None:
    """Return a valid decrypted access token, refreshing if needed.

    Steps:
    1. Load the OAuthToken row from DB. If none, return None.
    2. Decrypt the access token.
    3. If it expires more than 5 minutes in the future, return it.
    4. Acquire the refresh lock. Re-check expiry (another thread may have
       already refreshed). If still expired, attempt refresh using the
       refresh token.
    5. If the refresh token is also expired, return None.
    6. On refresh success, store the new tokens and return the new access token.
    7. On refresh failure, log the error and return None.

    Args:
        db: SQLAlchemy session.

    Returns:
        Decrypted access token string, or None if not connected or refresh failed.
    """
    row = db.query(OAuthToken).filter(OAuthToken.provider == "linkedin").first()
    if not row:
        return None

    now = datetime.now(timezone.utc)

    # Make expires_at timezone-aware if needed (SQLite stores naive datetimes).
    access_expires_at = row.access_token_expires_at
    if access_expires_at.tzinfo is None:
        access_expires_at = access_expires_at.replace(tzinfo=timezone.utc)

    refresh_expires_at = row.refresh_token_expires_at
    if refresh_expires_at.tzinfo is None:
        refresh_expires_at = refresh_expires_at.replace(tzinfo=timezone.utc)

    buffer = timedelta(seconds=_REFRESH_BUFFER_SECONDS)

    # Fast path: access token is still valid.
    if access_expires_at - now > buffer:
        decrypted = decrypt_token(row.access_token_encrypted)
        return decrypted  # None if key was rotated

    # Access token is expired or near expiry. Acquire lock before refreshing.
    with _refresh_lock:
        # Re-read from DB inside lock: another thread may have already refreshed.
        db.refresh(row)
        access_expires_at = row.access_token_expires_at
        if access_expires_at.tzinfo is None:
            access_expires_at = access_expires_at.replace(tzinfo=timezone.utc)

        if access_expires_at - now > buffer:
            # Another thread refreshed while we waited for the lock.
            return decrypt_token(row.access_token_encrypted)

        # Check refresh token expiry.
        if refresh_expires_at <= now:
            logger.warning("Refresh token is expired. Re-authorization required.")
            return None

        decrypted_refresh = decrypt_token(row.refresh_token_encrypted)
        if decrypted_refresh is None:
            logger.warning("Refresh token decryption failed. Re-authorization required.")
            return None

        try:
            new_token_response = refresh_access_token(decrypted_refresh)
        except OAuthTokenExchangeError as e:
            logger.error("Token refresh failed: %s", e)
            return None

        store_tokens(db, new_token_response)
        # Re-read after store to get fresh encrypted value.
        db.refresh(row)
        return decrypt_token(row.access_token_encrypted)


# ---------------------------------------------------------------------------
# Auth Status
# ---------------------------------------------------------------------------


def get_auth_status(db: Session) -> AuthStatus:
    """Return the current OAuth connection status.

    Args:
        db: SQLAlchemy session.

    Returns:
        AuthStatus dataclass with connection details.
    """
    row = db.query(OAuthToken).filter(OAuthToken.provider == "linkedin").first()
    if not row:
        return AuthStatus(connected=False)

    now = datetime.now(timezone.utc)

    access_expires_at = row.access_token_expires_at
    if access_expires_at.tzinfo is None:
        access_expires_at = access_expires_at.replace(tzinfo=timezone.utc)

    refresh_expires_at = row.refresh_token_expires_at
    if refresh_expires_at.tzinfo is None:
        refresh_expires_at = refresh_expires_at.replace(tzinfo=timezone.utc)

    needs_reauth = refresh_expires_at <= now

    # Attempt to decrypt to confirm the key is still valid.
    decrypted = decrypt_token(row.access_token_encrypted)
    if decrypted is None:
        # Key was rotated; treat as not connected.
        return AuthStatus(connected=False, needs_reauth=True)

    return AuthStatus(
        connected=True,
        expires_at=access_expires_at,
        refresh_expires_at=refresh_expires_at,
        scopes=row.scopes.split() if row.scopes else [],
        needs_reauth=needs_reauth,
        member_id=row.linkedin_member_id,
    )


# ---------------------------------------------------------------------------
# Token Revocation
# ---------------------------------------------------------------------------


def revoke_tokens(db: Session) -> None:
    """Delete the stored token row from the database.

    LinkedIn does not have a token revocation endpoint, so this simply
    removes the local token record. The access token will remain valid on
    LinkedIn's side until it expires naturally.

    Args:
        db: SQLAlchemy session.
    """
    row = db.query(OAuthToken).filter(OAuthToken.provider == "linkedin").first()
    if row:
        db.delete(row)
        db.commit()
