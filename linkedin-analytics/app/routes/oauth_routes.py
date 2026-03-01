"""OAuth route handlers: authorize, callback, disconnect, auth status API.

Routes:
  GET  /oauth/authorize   -> Redirect to LinkedIn authorization page
  GET  /oauth/callback    -> Handle LinkedIn redirect, exchange code, store tokens
  POST /oauth/disconnect  -> Delete stored tokens (CSRF-protected)
  GET  /api/auth/status   -> JSON endpoint returning current auth status
"""

import logging
import secrets

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_session
from app.oauth import (
    OAuthTokenExchangeError,
    build_authorization_url,
    exchange_code_for_tokens,
    generate_disconnect_csrf_token,
    generate_state,
    get_auth_status,
    revoke_tokens,
    sign_state,
    store_tokens,
    verify_disconnect_csrf_token,
    verify_state_signature,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Cookie names
_STATE_COOKIE = "oauth_state"
_NONCE_COOKIE = "disconnect_nonce"

# State cookie max age: 10 minutes.
_STATE_COOKIE_MAX_AGE = 600


def _oauth_disabled_response() -> JSONResponse:
    """Return a 404 JSON response when OAuth is not configured."""
    return JSONResponse(
        status_code=404,
        content={"detail": "OAuth is not configured. Set LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET, and TOKEN_ENCRYPTION_KEY."},
    )


@router.get("/oauth/authorize")
async def oauth_authorize(response: Response) -> RedirectResponse:
    """Initiate the LinkedIn OAuth 2.0 authorization flow.

    Generates a random state token, HMAC-signs it, stores the signature in an
    HttpOnly SameSite=Lax cookie, then redirects the user to LinkedIn's
    authorization page.

    Returns 404 if OAuth is not configured.
    """
    if not settings.oauth_enabled:
        return _oauth_disabled_response()

    state = generate_state()
    signature = sign_state(state)

    redirect_url = build_authorization_url(state)

    redirect_response = RedirectResponse(url=redirect_url, status_code=307)
    redirect_response.set_cookie(
        key=_STATE_COOKIE,
        value=signature,
        max_age=_STATE_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,  # Allow localhost (HTTP). Production should set secure=True.
    )
    # Store state value in a separate cookie so we can re-derive the signature
    # in the callback. The signature in _STATE_COOKIE is what we verify against.
    redirect_response.set_cookie(
        key="oauth_state_value",
        value=state,
        max_age=_STATE_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return redirect_response


@router.get("/oauth/callback")
async def oauth_callback(
    request: Request,
    db: Session = Depends(get_session),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> RedirectResponse:
    """Handle the LinkedIn OAuth callback.

    Validates the HMAC-signed state parameter from the cookie, exchanges the
    authorization code for tokens, encrypts and stores them, then redirects to
    the settings page with a success or error message.

    Returns 403 if the state parameter is missing or invalid (CSRF protection).
    Returns 404 if OAuth is not configured.
    """
    if not settings.oauth_enabled:
        return _oauth_disabled_response()

    # Handle user-denied authorization.
    if error:
        logger.warning("OAuth callback received error: %s", error)
        return RedirectResponse(
            url=f"/dashboard/settings?error={error}",
            status_code=302,
        )

    # Validate state parameter (CSRF protection).
    stored_signature = request.cookies.get(_STATE_COOKIE)
    stored_state = request.cookies.get("oauth_state_value")

    if not state or not stored_signature or not stored_state:
        logger.warning("OAuth callback: missing state or signature cookie.")
        return HTMLResponse(
            content="<h1>403 Forbidden</h1><p>Missing OAuth state parameter. Please try connecting again.</p>",
            status_code=403,
        )

    # Verify the state we received matches what we sent.
    if state != stored_state:
        logger.warning("OAuth callback: state mismatch (received vs stored).")
        return HTMLResponse(
            content="<h1>403 Forbidden</h1><p>OAuth state mismatch. Possible CSRF attack. Please try connecting again.</p>",
            status_code=403,
        )

    # Verify the HMAC signature of the state value.
    if not verify_state_signature(state, stored_signature):
        logger.warning("OAuth callback: HMAC state signature verification failed.")
        return HTMLResponse(
            content="<h1>403 Forbidden</h1><p>OAuth state signature invalid. Please try connecting again.</p>",
            status_code=403,
        )

    if not code:
        logger.warning("OAuth callback: no authorization code in request.")
        return HTMLResponse(
            content="<h1>400 Bad Request</h1><p>No authorization code received.</p>",
            status_code=400,
        )

    # Exchange code for tokens.
    try:
        token_response = exchange_code_for_tokens(code)
    except OAuthTokenExchangeError as e:
        logger.error("Token exchange failed: %s", e)
        redirect = RedirectResponse(
            url="/dashboard/settings?error=token_exchange_failed",
            status_code=302,
        )
        _clear_oauth_cookies(redirect)
        return redirect

    # Fetch the member ID immediately using the new access token, BEFORE storing tokens.
    # This eliminates the window where a token row exists without a linkedin_member_id.
    from app.linkedin_client import get_member_id
    member_id = await get_member_id(token_response.access_token)
    if not member_id:
        logger.warning(
            "Could not fetch member ID from /userinfo during callback. "
            "Publishing will be unavailable until reconnection."
        )

    store_tokens(db, token_response, member_id=member_id)

    logger.info("LinkedIn OAuth tokens stored successfully.")

    redirect = RedirectResponse(
        url="/dashboard/settings?connected=1",
        status_code=302,
    )
    _clear_oauth_cookies(redirect)
    return redirect


@router.post("/oauth/disconnect")
async def oauth_disconnect(
    request: Request,
    db: Session = Depends(get_session),
    csrf_token: str | None = Form(default=None),
) -> RedirectResponse:
    """Delete stored LinkedIn tokens (CSRF-protected).

    The disconnect form renders a hidden CSRF token generated from a nonce
    stored in a cookie. This endpoint validates the token before deleting.

    Returns 403 if the CSRF token is missing or invalid.
    Returns 404 if OAuth is not configured.
    """
    if not settings.oauth_enabled:
        return _oauth_disabled_response()

    nonce = request.cookies.get(_NONCE_COOKIE)

    if not csrf_token or not nonce:
        logger.warning("Disconnect request missing CSRF token or nonce cookie.")
        return HTMLResponse(
            content="<h1>403 Forbidden</h1><p>Missing CSRF token. Please try again from the settings page.</p>",
            status_code=403,
        )

    if not verify_disconnect_csrf_token(nonce, csrf_token):
        logger.warning("Disconnect request: CSRF token verification failed.")
        return HTMLResponse(
            content="<h1>403 Forbidden</h1><p>Invalid CSRF token. Please try again from the settings page.</p>",
            status_code=403,
        )

    revoke_tokens(db)
    logger.info("LinkedIn OAuth tokens revoked.")

    redirect = RedirectResponse(
        url="/dashboard/settings?disconnected=1",
        status_code=302,
    )
    # Clear the nonce cookie after use.
    redirect.delete_cookie(_NONCE_COOKIE)
    return redirect


@router.get("/api/auth/status")
async def auth_status_api(
    db: Session = Depends(get_session),
) -> JSONResponse:
    """Return the current OAuth connection status as JSON.

    Used by the future data sync plan to check connection before pulling data.
    Returns 404 if OAuth is not configured.
    """
    if not settings.oauth_enabled:
        return JSONResponse(
            status_code=200,
            content={
                "oauth_configured": False,
                "connected": False,
                "message": "OAuth is not configured.",
            },
        )

    status = get_auth_status(db)

    return JSONResponse(
        content={
            "oauth_configured": True,
            "connected": status.connected,
            "needs_reauth": status.needs_reauth,
            "member_id": status.member_id,
            "scopes": status.scopes,
            "expires_at": status.expires_at.isoformat() if status.expires_at else None,
            "refresh_expires_at": (
                status.refresh_expires_at.isoformat()
                if status.refresh_expires_at
                else None
            ),
        }
    )


def _clear_oauth_cookies(response: RedirectResponse) -> None:
    """Delete the OAuth state cookies after the callback completes."""
    response.delete_cookie(_STATE_COOKIE)
    response.delete_cookie("oauth_state_value")


def generate_nonce_cookie(response: Response) -> str:
    """Generate a disconnect nonce, set it as a cookie, and return the value.

    Called by the settings route to set up CSRF protection for the disconnect
    form before rendering the page.
    """
    nonce = secrets.token_urlsafe(32)
    response.set_cookie(
        key=_NONCE_COOKIE,
        value=nonce,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return nonce
