# Technical Implementation Plan: LinkedIn OAuth Auth Setup

**Feature:** OAuth 2.0 authorization code flow for the LinkedIn Analytics Dashboard
**Created:** 2026-03-01
**Author:** Architect
**Revised:** 2026-03-01 (addressing red team, feasibility, and librarian review findings)

---

## Context Alignment

### CLAUDE.md Patterns Followed
- **Existing stack:** FastAPI + SQLAlchemy + SQLite + Jinja2 + Tailwind CDN + Pydantic Settings. No new frameworks introduced. The only new dependency is `cryptography` for Fernet token encryption.
- **Config via Pydantic Settings:** New env vars (`LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `TOKEN_ENCRYPTION_KEY`, `LINKEDIN_API_VERSION`) added to the existing `Settings` class, loaded from `.env`.
- **Graceful degradation:** If `LINKEDIN_CLIENT_ID` is not set, all OAuth UI elements are hidden and the dashboard operates exactly as it does today with manual XLSX uploads.
- **Dark theme consistency:** New OAuth-related UI (status indicator, connect button, settings page) uses the existing Navy/card/accent color palette and Inter/JetBrains Mono fonts.
- **Sensitivity protocol:** No employer-identifiable data. OAuth tokens are stored encrypted. Client secrets are in `.env` (gitignored). No token values in logs.
- **No em-dashes:** All copy in this plan and templates avoids em-dashes.
- **Single-user, self-hosted:** No multi-tenant OAuth. One LinkedIn account, one set of tokens.
- **httpx already in requirements.txt:** Used for all outbound HTTP calls to LinkedIn OAuth endpoints.

### Prior Plans Consulted
- `plans/linkedin-analytics-dashboard.md` (APPROVED): Established the full architecture. Explicitly listed "Phase 3: API Integration (future, requires legal entity)" with "Add LinkedIn OAuth flow" as the first item. The OAuth flow itself does not require Community Management API access; it works with just `openid profile` scopes (auto-granted with "Share on LinkedIn"). Community Management API approval is still pending and only required by the future data sync plan, not this auth plan. This plan implements Phase 3's OAuth component only.
- `plans/engagement-analytics.md` (APPROVED): Established the pattern for adding new columns via migration scripts (not Alembic), new API endpoints, new templates, and new routes. This plan follows the same migration script pattern.
- `plans/bksp-ca-astro-cloudflare-blog.md`: Reviewed for scope conflicts; no overlap with the Astro blog plan.
- `.claude/agents/linkedin-api-architect.md`: Defines design principles for OAuth integration: token encryption at rest (Fernet), separation of concerns (OAuth module vs. API client), graceful degradation, token lifecycle management, API versioning, and rate limiting. This plan implements all of these.

### Deviations from Established Patterns
- **New dependency (`cryptography`):** The project has avoided adding dependencies beyond what was in the original plan. `cryptography` is required for Fernet symmetric encryption of OAuth tokens at rest. This is a non-negotiable security requirement per the linkedin-api-architect agent rules. The package is mature, well-maintained, and has no transitive dependency conflicts with the existing stack.
- **New SQLAlchemy model (`OAuthToken`):** Unlike prior changes that extended existing models, this adds a new table. Justification: OAuth tokens are a fundamentally different concern from content analytics. A separate model keeps the token lifecycle isolated and simplifies encryption/decryption logic.

---

## Goals

1. Implement LinkedIn OAuth 2.0 authorization code flow (redirect, callback, token exchange)
2. Store access tokens and refresh tokens encrypted at rest in SQLite using Fernet symmetric encryption
3. Implement token lifecycle management: automatic refresh before expiry, expiry warnings, revocation handling
4. Provide a UI for connecting/disconnecting the LinkedIn account with clear status indicators
5. Add a settings page showing connection status, token expiry, granted scopes, and a disconnect button
6. Ensure the dashboard continues to work without OAuth configured (graceful degradation)

## Non-Goals

- **API data sync:** Pulling posts, analytics, followers, or demographics via the LinkedIn API. That is a separate follow-up plan.
- **Multi-account support:** Only one LinkedIn account can be connected at a time.
- **PKCE:** LinkedIn's authorization code flow does not require PKCE for server-side apps. The state parameter provides CSRF protection.
- **Webhook/push notifications:** LinkedIn does not offer webhooks for analytics. Polling will be designed in the data sync plan.
- **Automated scheduled token refresh:** The refresh happens on-demand when the dashboard detects the access token is expired or near-expiry. No background scheduler is needed for the auth-only scope.

## Assumptions

1. The user has created a LinkedIn business page and registered a developer application at https://developer.linkedin.com
2. The developer app has "Share on LinkedIn" (auto-granted) and "Community Management API" (Development tier) products enabled
3. The redirect URI configured in the LinkedIn developer portal matches the dashboard's callback URL (e.g., `http://localhost:8050/oauth/callback`)
4. The `TOKEN_ENCRYPTION_KEY` env var is a Fernet key generated by the user (documented in setup instructions). If not set, OAuth features are disabled. The key is validated at startup (see Section 7).
5. The dashboard runs behind HTTPS in production or is accessed only via localhost during development. LinkedIn requires HTTPS redirect URIs for production apps, but allows `http://localhost` for development.
6. The SQLite database is accessible only to the dashboard process (file permissions). Encrypted tokens add defense-in-depth, not primary access control.

## Proposed Design

### Architecture Overview

```
User clicks "Connect LinkedIn" on Settings page
    |
    v
GET /oauth/authorize
    |-- Generate random state token
    |-- HMAC-sign the state with TOKEN_ENCRYPTION_KEY and store in HttpOnly cookie
    |-- Build LinkedIn authorization URL with scopes
    |-- Redirect user to LinkedIn
    |
    v
User authorizes on LinkedIn, LinkedIn redirects to:
GET /oauth/callback?code=xxx&state=yyy
    |-- Validate state parameter: HMAC-sign the received state, compare to cookie value
    |-- Exchange authorization code for tokens via POST to LinkedIn
    |-- Encrypt tokens with Fernet
    |-- Store encrypted tokens in oauth_tokens table
    |-- Redirect to /dashboard/settings with success message
    |
    v
On any API request (future data sync plan):
    |-- Load encrypted tokens from DB
    |-- Decrypt access token
    |-- Acquire refresh lock before checking expiry
    |-- Check if expired (60-day lifetime)
    |   |-- If expired: use refresh token to get new access token
    |   |-- If refresh token also expired (365-day lifetime): show re-auth prompt
    |-- Release refresh lock
    |-- Use access token in Authorization header
```

### Module Structure

```
linkedin-analytics/app/
  oauth.py              # NEW: OAuth flow logic (authorize URL, callback handler,
                        #       token exchange, token refresh, encryption/decryption)
  routes/
    oauth_routes.py     # NEW: FastAPI routes for /oauth/* endpoints and /api/auth/status
    dashboard.py        # MODIFIED: Add /dashboard/settings route, inject auth status
  models.py             # MODIFIED: Add OAuthToken model
  config.py             # MODIFIED: Add LinkedIn OAuth settings with Fernet key validation
  templates/
    settings.html       # NEW: Settings page with OAuth status and connect/disconnect
    base.html           # MODIFIED: Add "Settings" nav item, connection status indicator
```

### 1. Configuration (`app/config.py`)

Add four new optional settings to the `Settings` class:

```python
# LinkedIn OAuth (all optional; if client_id is empty, OAuth features are disabled)
linkedin_client_id: str = ""
linkedin_client_secret: str = ""
token_encryption_key: str = ""          # Fernet key (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
linkedin_api_version: str = "202601"    # LinkedIn API version header
linkedin_redirect_uri: str = "http://localhost:8050/oauth/callback"

@field_validator("token_encryption_key")
@classmethod
def validate_fernet_key(cls, v: str) -> str:
    """Validate that the token encryption key is a valid Fernet key at startup.

    If the key is empty, OAuth is disabled (no error). If the key is set but
    invalid, fail fast with a clear error rather than crashing mid-token-exchange.
    """
    if not v:
        return v
    try:
        from cryptography.fernet import Fernet
        Fernet(v.encode())
    except Exception as e:
        raise ValueError(
            f"TOKEN_ENCRYPTION_KEY is not a valid Fernet key: {e}. "
            f"Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return v

@property
def oauth_enabled(self) -> bool:
    """Return True if LinkedIn OAuth is fully configured."""
    return bool(self.linkedin_client_id and self.linkedin_client_secret and self.token_encryption_key)
```

**Startup redirect URI validation:** When the app starts and `oauth_enabled` is True, validate that the path component of `linkedin_redirect_uri` matches the registered `/oauth/callback` route. Log a warning if the host is not `localhost`. This prevents silent misconfiguration where authorization codes are sent to the wrong destination.

```python
# In app startup (main.py or oauth.py init)
from urllib.parse import urlparse

def validate_redirect_uri(settings: Settings) -> None:
    """Validate redirect URI path matches the callback route at startup."""
    parsed = urlparse(settings.linkedin_redirect_uri)
    if parsed.path != "/oauth/callback":
        raise ValueError(
            f"LINKEDIN_REDIRECT_URI path must be '/oauth/callback', got '{parsed.path}'"
        )
    if parsed.hostname not in ("localhost", "127.0.0.1"):
        import logging
        logging.getLogger(__name__).warning(
            "LINKEDIN_REDIRECT_URI host is '%s', not localhost. "
            "Ensure HTTPS is configured and the URI matches the LinkedIn developer portal.",
            parsed.hostname,
        )
```

### 2. Token Storage Model (`app/models.py`)

New `OAuthToken` model:

```python
class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    provider: str = Column(String, nullable=False, default="linkedin", unique=True)
    access_token_encrypted: str = Column(String, nullable=False)
    refresh_token_encrypted: str = Column(String, nullable=False)
    access_token_expires_at: datetime = Column(DateTime, nullable=False)
    refresh_token_expires_at: datetime = Column(DateTime, nullable=False)
    scopes: str = Column(String, nullable=False)         # space-separated scope list
    linkedin_member_id: str | None = Column(String, nullable=True)  # URN sub from /userinfo
    created_at: datetime = Column(DateTime, default=func.now())
    updated_at: datetime = Column(DateTime, default=func.now(), onupdate=func.now())
```

Single-user design: there is at most one row in this table with `provider="linkedin"`. The `unique=True` constraint on `provider` enforces this at the database level, preventing duplicate rows from upsert bugs. On re-authorization, the existing row is updated (upsert pattern).

### 3. OAuth Module (`app/oauth.py`)

Core functions:

- `build_authorization_url(state: str) -> str`: Constructs the LinkedIn authorization URL with `response_type=code`, `client_id`, `redirect_uri`, `scope`, and `state`.
- `exchange_code_for_tokens(code: str) -> TokenResponse`: POSTs to `https://www.linkedin.com/oauth/v2/accessToken` with `grant_type=authorization_code`. Uses explicit exception handling to prevent leaking `client_secret` (see Section 9).
- `refresh_access_token(refresh_token: str) -> TokenResponse`: POSTs with `grant_type=refresh_token`. Same exception sanitization as `exchange_code_for_tokens`.
- `sign_state(state: str) -> str`: HMAC-signs the state value using `TOKEN_ENCRYPTION_KEY` (see Section 4 for details).
- `verify_state_signature(state: str, signature: str) -> bool`: Verifies the HMAC signature.
- `encrypt_token(plaintext: str) -> str`: Encrypts with Fernet, returns base64 string.
- `decrypt_token(ciphertext: str) -> str`: Decrypts with Fernet, returns plaintext.
- `store_tokens(db: Session, token_response: TokenResponse) -> OAuthToken`: Encrypts and upserts tokens in the DB.
- `get_valid_access_token(db: Session) -> str | None`: Loads token from DB, acquires refresh lock, checks expiry, refreshes if needed, returns decrypted access token or None. See Section 8 for locking details.
- `get_auth_status(db: Session) -> AuthStatus`: Returns a dataclass with `connected: bool`, `expires_at: datetime | None`, `refresh_expires_at: datetime | None`, `scopes: list[str]`, `needs_reauth: bool`, `member_id: str | None`.
- `revoke_tokens(db: Session) -> None`: Deletes the token row from the DB (LinkedIn does not have a token revocation endpoint).

Scopes requested: `openid profile` initially. The scope `r_member_postAnalytics` (or the correct scope name per current LinkedIn API documentation) will be added in the data sync plan once Community Management API access is confirmed. The scope name should be verified against https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-overview at implementation time, as LinkedIn has changed scope names several times.

The `openid` and `profile` scopes come with "Share on LinkedIn" (auto-granted). Community Management API scopes require separate approval.

### 4. OAuth Routes (`app/routes/oauth_routes.py`)

```
GET  /oauth/authorize    -> Redirect to LinkedIn authorization page
GET  /oauth/callback     -> Handle LinkedIn redirect, exchange code, store tokens
POST /oauth/disconnect   -> Delete stored tokens (CSRF-protected), redirect to settings
GET  /api/auth/status    -> JSON endpoint returning current auth status (for future use by data sync)
```

The `/dashboard/settings` route is registered in `app/routes/dashboard.py` (not `oauth_routes.py`) to follow the existing convention where all `/dashboard/*` routes live in `dashboard.py`. The settings route imports `get_auth_status` from `oauth.py` to inject connection status into the template.

**State cookie signing (CSRF protection for the authorize flow):**
- Generate a random 32-byte hex state token
- HMAC-sign the state using `TOKEN_ENCRYPTION_KEY` via `hmac.new(key, state.encode(), hashlib.sha256)`. This reuses the existing Fernet key material for signing, avoiding a new dependency or env var.
- Store the HMAC signature in an HttpOnly, SameSite=Lax cookie (`oauth_state`) with a 10-minute max-age
- On callback, HMAC-sign the received `state` query parameter and compare to the cookie value using `hmac.compare_digest()`
- Delete the cookie after validation
- If the app restarts between the authorization redirect and the callback, the HMAC key is unchanged (it comes from the environment), so the callback will still validate correctly.

**CSRF protection for POST /oauth/disconnect:**
- Render a hidden CSRF token in the disconnect form. The token is generated as `hmac.new(key, "disconnect:" + session_nonce, hashlib.sha256).hexdigest()` where `session_nonce` is a random value stored in a cookie set when the settings page is rendered.
- On POST, validate the CSRF token by recomputing the HMAC from the cookie nonce and comparing with `hmac.compare_digest()`.
- Reject the request with 403 if the CSRF token is missing or invalid.

**Error handling:**
- If the user denies authorization, LinkedIn redirects with `error=user_cancelled_authorize`. Display a user-friendly message on the settings page.
- If the code exchange fails (network error, invalid code), log only the HTTP status code and a sanitized error message. Never log the request body or headers, which may contain `client_secret`. See Section 9.
- If the state parameter does not match, reject the callback with a 403 and log a CSRF warning.

### 5. Settings Page (`app/templates/settings.html`)

Displays:
- **Connection status:** "Connected" (green) or "Not connected" (muted)
- **LinkedIn member ID:** If connected, show the member URN (e.g., `urn:li:person:abc123`)
- **Access token expiry:** Date and "expires in X days" relative display
- **Refresh token expiry:** Date and "expires in X days" relative display
- **Warning banner:** If refresh token expires within 30 days, show an amber warning prompting re-authorization
- **Granted scopes:** List of scopes the token was issued with
- **Connect button:** If not connected, shows "Connect LinkedIn Account" button
- **Disconnect button:** If connected, shows "Disconnect" button with confirmation dialog. The form includes a hidden CSRF token field.
- **Setup instructions:** If OAuth is not configured (no client_id in env), show a collapsed instructions section explaining what env vars to set

### 6. Navigation Update (`app/templates/base.html`)

Add a "Settings" nav item to the sidebar, below "Upload":
```python
("/dashboard/settings", "Settings", "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"),
```

Also add a small connection status indicator dot in the sidebar footer (green if connected, hidden if OAuth not configured).

### 7. Token Encryption

- Use `cryptography.fernet.Fernet` with the key from `TOKEN_ENCRYPTION_KEY` env var
- The Fernet key is 32 bytes, URL-safe base64-encoded (44 characters)
- Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- The key is validated at startup via a Pydantic `field_validator` on the `Settings` class (see Section 1). If the key is set but malformed, the app fails to start with a clear error message rather than crashing mid-token-exchange.
- If `TOKEN_ENCRYPTION_KEY` is not set, `oauth_enabled` returns False and all OAuth routes return 404
- If the key is rotated (old key replaced with a new one), existing encrypted tokens become undecryptable. The app handles this gracefully: `decrypt_token` catches `InvalidToken` exceptions and treats them as "not connected," prompting re-authorization.

### 8. Token Refresh Strategy

When `get_valid_access_token()` is called:
1. Load the OAuthToken row from DB
2. If no row exists, return None (not connected)
3. Decrypt the access token
4. If `access_token_expires_at` is more than 5 minutes in the future, return the access token
5. If `access_token_expires_at` is within 5 minutes or past, attempt refresh:
   a. Acquire an in-process `threading.Lock` (`_refresh_lock`) to prevent concurrent refresh attempts. If the lock is already held, wait for it, then re-check the token expiry (another thread may have already refreshed).
   b. Decrypt the refresh token
   c. If `refresh_token_expires_at` is past, return None and set `needs_reauth` flag
   d. Call `refresh_access_token()` with the decrypted refresh token
   e. Encrypt the new access token and update the DB row
   f. Release the lock
   g. Return the new access token
6. If the refresh call fails (network error, invalid_grant), log the error and return None

The lock prevents the race condition where concurrent requests both detect an expired token and both attempt to refresh, potentially invalidating each other's refresh tokens. The lock is a simple `threading.Lock` since the app runs as a single process.

This on-demand refresh means no background process is needed. The token is refreshed the first time it is needed after expiry.

### 9. Exception Sanitization for HTTP Calls

All outbound HTTP calls to LinkedIn's OAuth endpoints (`exchange_code_for_tokens`, `refresh_access_token`) are wrapped in a try/except that catches `httpx.HTTPError` and its subclasses. The exception handler:

- Logs only the HTTP status code and a generic error description (e.g., "Token exchange failed with status 400")
- Never logs the request body, headers, or URL query parameters, which may contain `client_secret`
- Re-raises a sanitized application-level exception (e.g., `OAuthTokenExchangeError`) with only the status code and a safe message
- Ensures `debug=False` in production; even in development, the sanitized exception prevents `client_secret` from appearing in stack traces

```python
try:
    response = httpx.post(token_url, data=payload, timeout=httpx.Timeout(10.0))
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    logger.error("Token exchange failed with status %d", e.response.status_code)
    raise OAuthTokenExchangeError(f"LinkedIn returned status {e.response.status_code}") from None
except httpx.HTTPError:
    logger.error("Token exchange failed: network error")
    raise OAuthTokenExchangeError("Network error during token exchange") from None
```

The `from None` suppresses the original exception chain, which would otherwise include the httpx request object containing sensitive data.

---

## Interfaces / Schema Changes

### New Table: `oauth_tokens`

| Column | Type | Constraints |
|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| provider | TEXT | NOT NULL DEFAULT 'linkedin' UNIQUE |
| access_token_encrypted | TEXT | NOT NULL |
| refresh_token_encrypted | TEXT | NOT NULL |
| access_token_expires_at | DATETIME | NOT NULL |
| refresh_token_expires_at | DATETIME | NOT NULL |
| scopes | TEXT | NOT NULL |
| linkedin_member_id | TEXT | NULLABLE |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |
| updated_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |

### New Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `LINKEDIN_CLIENT_ID` | No | `""` | LinkedIn developer app client ID |
| `LINKEDIN_CLIENT_SECRET` | No | `""` | LinkedIn developer app client secret |
| `TOKEN_ENCRYPTION_KEY` | No | `""` | Fernet key for encrypting tokens at rest. Validated at startup. |
| `LINKEDIN_API_VERSION` | No | `"202601"` | LinkedIn API version header value |
| `LINKEDIN_REDIRECT_URI` | No | `"http://localhost:8050/oauth/callback"` | OAuth callback URL. Path must be `/oauth/callback`. Production deployments must use HTTPS. Must exactly match the redirect URI registered in the LinkedIn developer portal. |

### New API Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/oauth/authorize` | Initiate OAuth flow (redirect to LinkedIn) |
| GET | `/oauth/callback` | Handle LinkedIn redirect, exchange code for tokens |
| POST | `/oauth/disconnect` | Delete stored tokens (CSRF-protected) |
| GET | `/dashboard/settings` | Render settings page with auth status (in `dashboard.py`) |
| GET | `/api/auth/status` | JSON endpoint returning current auth status (for future use by data sync) |

### New Dependency

```
cryptography>=43.0.0
```

---

## Data Migration

### Migration Script: `scripts/add_oauth_tokens_table.py`

Since the project uses `Base.metadata.create_all()` on startup and does not use Alembic, the new `oauth_tokens` table will be created automatically when `OAuthToken` is added to `models.py` and the app starts. No manual migration script is needed for this change (unlike the engagement-analytics plan which added columns to an existing table).

`create_all()` only creates tables that do not exist. It does not modify existing tables. Since `oauth_tokens` is a new table, `create_all()` handles it correctly.

**No migration script required.**

---

## Rollout Plan

### Phase 1: Core OAuth (this plan)

1. Add `cryptography` to `requirements.txt`
2. Add OAuth settings to `config.py` with Fernet key `field_validator` and redirect URI validation
3. Add `OAuthToken` model to `models.py` (with `unique=True` on `provider`)
4. Create `app/oauth.py` with token encryption, exchange, refresh (with `threading.Lock`), status logic, HMAC state signing, and exception sanitization
5. Create `app/routes/oauth_routes.py` with authorize, callback, disconnect (CSRF-protected), and auth status routes
6. Add `/dashboard/settings` route to `app/routes/dashboard.py`
7. Create `app/templates/settings.html` with connection status UI and CSRF token in disconnect form
8. Update `app/templates/base.html` with Settings nav link and status indicator
9. Update `app/main.py` to include the new oauth_routes router and run redirect URI validation on startup
10. Update `.env.example` with new env vars (commented out), including `LINKEDIN_REDIRECT_URI` and a note that production must use HTTPS
11. Write tests

### Prerequisites for Testing with Real LinkedIn

1. Create a LinkedIn Page (business page)
2. Register a developer app at https://developer.linkedin.com
3. Add "Share on LinkedIn" product (auto-granted)
4. Request "Community Management API" Development tier access
5. Set the OAuth 2.0 redirect URL to `http://localhost:8050/oauth/callback`
6. Copy the client ID and client secret to `.env`
7. Generate a Fernet key and add it to `.env`

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LinkedIn rejects Community Management API application | Medium | High (blocks future data sync, not this plan) | "Share on LinkedIn" is auto-granted and sufficient for the OAuth flow itself. This auth plan uses only `openid profile` scopes. The data sync plan depends on Community Management API approval. |
| LinkedIn changes OAuth endpoints or token lifetimes | Low | Medium | API version is pinned in config. Token lifetimes are read from the token response, not hardcoded. |
| Fernet key lost or rotated | Low | High (tokens become undecryptable) | Document key backup in setup instructions. If key is lost, user simply re-authorizes (clicks "Connect" again). `decrypt_token` catches `InvalidToken` and treats it as "not connected." |
| Token encryption key committed to git | Low | High | `.env` is in `.gitignore`. The `.env.example` file contains only placeholder comments, not real values. |
| CSRF attack on OAuth callback | Low | Medium | State parameter HMAC-signed with `TOKEN_ENCRYPTION_KEY`, stored in HttpOnly/SameSite=Lax cookie, validated on callback with `hmac.compare_digest()`. 10-minute expiry. |
| CSRF attack on disconnect endpoint | Low | Medium | CSRF token rendered in form, validated server-side via HMAC. Requests without valid token are rejected with 403. |
| Token refresh race condition from concurrent requests | Low | Medium | In-process `threading.Lock` around the refresh operation. After acquiring lock, re-check token expiry to avoid redundant refresh. |
| `client_secret` leaked via error logs or stack traces | Low | High | All httpx exceptions caught and re-raised as sanitized application exceptions using `from None`. Only HTTP status codes logged. |
| SQLite concurrent write contention during token refresh | Low | Low | Single-user app; WAL mode handles concurrent reads. Token writes are infrequent (once every 60 days). Lock prevents concurrent writes. |

---

## Test Plan

### Test Command

```bash
cd ~/bksp/linkedin-analytics && python -m pytest tests/ -v
```

### Unit Tests (`tests/test_oauth.py`)

1. **`test_build_authorization_url`**: Verify the URL includes correct client_id, redirect_uri, scopes, state, and response_type parameters.
2. **`test_build_authorization_url_uses_configured_redirect_uri`**: Verify that `build_authorization_url` uses the `linkedin_redirect_uri` value from settings.
3. **`test_encrypt_decrypt_token`**: Encrypt a token string, decrypt it, verify round-trip integrity.
4. **`test_encrypt_with_invalid_key`**: Verify that an invalid Fernet key raises an appropriate error at startup (settings validation).
5. **`test_fernet_key_validated_at_startup`**: Verify that a malformed `TOKEN_ENCRYPTION_KEY` causes `Settings` instantiation to fail with a clear error.
6. **`test_fernet_key_empty_disables_oauth`**: Verify that an empty key is allowed and `oauth_enabled` returns False.
7. **`test_decrypt_with_wrong_key_returns_none`**: Encrypt with key A, attempt decrypt with key B, verify graceful handling (not a crash).
8. **`test_store_tokens_creates_row`**: Store a token response, verify the DB row exists with encrypted values.
9. **`test_store_tokens_upserts_on_reauth`**: Store tokens twice, verify only one row exists with updated values.
10. **`test_get_auth_status_not_connected`**: With no tokens in DB, verify `connected=False`.
11. **`test_get_auth_status_connected`**: With valid tokens in DB, verify `connected=True`, correct expiry dates, and scopes.
12. **`test_get_auth_status_needs_reauth`**: With expired refresh token, verify `needs_reauth=True`.
13. **`test_get_valid_access_token_not_expired`**: With a token expiring in 30 days, verify the decrypted token is returned without a refresh call.
14. **`test_get_valid_access_token_expired_refresh_succeeds`**: With an expired access token but valid refresh token, mock the refresh HTTP call and verify new token is stored.
15. **`test_get_valid_access_token_refresh_token_expired`**: With both tokens expired, verify None is returned.
16. **`test_revoke_tokens_deletes_row`**: Store tokens then revoke, verify the DB row is deleted.
17. **`test_sign_and_verify_state`**: Sign a state value, verify the signature is accepted.
18. **`test_tampered_state_cookie_rejected`**: Sign a state value, modify the signature, verify it is rejected.
19. **`test_exception_sanitization_no_secret_in_error`**: Mock an httpx error with client_secret in the request body, verify the re-raised exception contains no sensitive data.
20. **`test_redirect_uri_path_validation`**: Verify that a redirect URI with a non-`/oauth/callback` path raises a ValueError at startup.

### Route Tests (`tests/test_oauth_routes.py`)

1. **`test_authorize_redirects_to_linkedin`**: GET `/oauth/authorize`, verify 307 redirect to `linkedin.com/oauth/v2/authorization` with correct query params.
2. **`test_authorize_sets_state_cookie`**: GET `/oauth/authorize`, verify `oauth_state` cookie is set with HMAC signature.
3. **`test_callback_exchanges_code`**: Mock the LinkedIn token endpoint, GET `/oauth/callback?code=xxx&state=yyy` with matching HMAC-signed state cookie, verify tokens are stored.
4. **`test_callback_rejects_mismatched_state`**: GET `/oauth/callback` with wrong state, verify 403.
5. **`test_callback_rejects_tampered_cookie`**: GET `/oauth/callback` with a forged cookie value (not HMAC-signed), verify 403.
6. **`test_callback_handles_user_denied`**: GET `/oauth/callback?error=user_cancelled_authorize`, verify redirect to settings with error message.
7. **`test_disconnect_deletes_tokens`**: POST `/oauth/disconnect` with valid CSRF token, verify token row is deleted and redirect to settings.
8. **`test_disconnect_rejects_missing_csrf_token`**: POST `/oauth/disconnect` without CSRF token, verify 403.
9. **`test_disconnect_rejects_invalid_csrf_token`**: POST `/oauth/disconnect` with forged CSRF token, verify 403.
10. **`test_settings_page_not_connected`**: GET `/dashboard/settings` with no tokens, verify "Not connected" status shown.
11. **`test_settings_page_connected`**: GET `/dashboard/settings` with tokens, verify "Connected" status and expiry info shown.
12. **`test_oauth_routes_404_when_not_configured`**: With `LINKEDIN_CLIENT_ID=""`, verify `/oauth/authorize` returns 404.
13. **`test_auth_status_api_endpoint`**: GET `/api/auth/status`, verify JSON response with connection status.

### Graceful Degradation Tests

1. **`test_dashboard_works_without_oauth_config`**: With no OAuth env vars set, verify `/dashboard` renders without errors.
2. **`test_settings_nav_hidden_without_oauth`**: With no OAuth config, verify the Settings nav link still appears but shows setup instructions instead of connect button.
3. **`test_upload_still_works_with_oauth`**: With OAuth configured, verify file upload still works normally.

---

## Acceptance Criteria

1. **OAuth flow completes end-to-end:** User can click "Connect LinkedIn", authorize on LinkedIn, and be redirected back to the settings page showing "Connected" status.
2. **Tokens are encrypted at rest:** Inspecting the `oauth_tokens` table directly shows only encrypted ciphertext, not plaintext tokens.
3. **Token refresh works:** When the access token expires, calling `get_valid_access_token()` automatically refreshes it using the refresh token. Concurrent refresh attempts are serialized by the refresh lock.
4. **Disconnect works:** User can click "Disconnect" on the settings page, confirming the action, and the token row is deleted. The disconnect form is CSRF-protected.
5. **Graceful degradation:** With no `LINKEDIN_CLIENT_ID` in the environment, the dashboard works exactly as before. No errors, no broken pages. The settings page shows setup instructions.
6. **CSRF protection:** The OAuth callback validates the HMAC-signed state parameter against the cookie. Mismatched state returns 403. The disconnect endpoint validates a CSRF token. Missing or invalid tokens return 403.
7. **No token leakage:** Tokens never appear in logs, URLs, or HTML source. Only token metadata (expiry, scopes) is logged or displayed. httpx exceptions are caught and re-raised without sensitive request data.
8. **Startup validation:** Invalid Fernet keys cause a clear startup error. Misconfigured redirect URI paths cause a startup error.
9. **All tests pass:** `python -m pytest tests/ -v` passes with no failures.
10. **Docker build succeeds:** `docker compose build` completes without errors with the new `cryptography` dependency.

---

## Task Breakdown

### Files to Create

| File | Purpose |
|---|---|
| `linkedin-analytics/app/oauth.py` | OAuth flow logic: URL building, token exchange, encryption, refresh (with lock), HMAC state signing, exception sanitization, status |
| `linkedin-analytics/app/routes/oauth_routes.py` | FastAPI routes for /oauth/authorize, /oauth/callback, /oauth/disconnect, /api/auth/status |
| `linkedin-analytics/app/templates/settings.html` | Settings page template with OAuth connection status UI and CSRF token in disconnect form |
| `linkedin-analytics/tests/test_oauth.py` | Unit tests for oauth.py functions |
| `linkedin-analytics/tests/test_oauth_routes.py` | Route tests for OAuth endpoints and settings page |

### Files to Modify

| File | Change |
|---|---|
| `linkedin-analytics/requirements.txt` | Add `cryptography>=43.0.0` |
| `linkedin-analytics/app/config.py` | Add OAuth settings with `field_validator` for Fernet key validation |
| `linkedin-analytics/app/models.py` | Add `OAuthToken` model with `unique=True` on `provider` |
| `linkedin-analytics/app/main.py` | Import and include `oauth_routes` router; call `validate_redirect_uri()` on startup |
| `linkedin-analytics/app/routes/dashboard.py` | Add `/dashboard/settings` route |
| `linkedin-analytics/app/templates/base.html` | Add "Settings" to sidebar nav_items list, add connection status indicator dot in sidebar footer |
| `linkedin-analytics/.env.example` | Add commented-out OAuth env vars with documentation, including `LINKEDIN_REDIRECT_URI` and HTTPS note |

### Implementation Order

1. `requirements.txt` (add cryptography)
2. `app/config.py` (add OAuth settings with Fernet key validator)
3. `app/models.py` (add OAuthToken model with unique constraint)
4. `app/oauth.py` (core OAuth logic with HMAC signing, refresh lock, exception sanitization)
5. `app/routes/oauth_routes.py` (OAuth route handlers with CSRF on disconnect)
6. `app/routes/dashboard.py` (add /dashboard/settings route)
7. `app/templates/settings.html` (settings page UI with CSRF token)
8. `app/templates/base.html` (nav update)
9. `app/main.py` (register router, add startup redirect URI validation)
10. `.env.example` (document new env vars)
11. `tests/test_oauth.py` (unit tests)
12. `tests/test_oauth_routes.py` (route tests)

## Status: APPROVED

<!-- Context Metadata
discovered_at: 2026-03-01T12:00:00Z
claude_md_exists: true
recent_plans_consulted: engagement-analytics.md, linkedin-analytics-dashboard.md, bksp-ca-astro-cloudflare-blog.md
archived_plans_consulted: engagement-analytics.feasibility.md, linkedin-analytics-dashboard.feasibility.md
-->
