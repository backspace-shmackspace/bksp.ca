# Red Team Review (Round 2): LinkedIn OAuth Auth Setup

**Plan reviewed:** `plans/linkedin-oauth-auth.md`
**Reviewed:** 2026-03-01
**Reviewer:** Security Red Team
**Round:** 2 (verifying fixes from Round 1)

---

## Verdict: PASS

All Critical and Major findings from Round 1 have been adequately addressed. No new Critical findings introduced. Two new Minor observations from the revisions.

---

## Verification of Round 1 Findings

### R1-1. Unsigned state cookie (was Critical) -- RESOLVED

The revised plan (Section 4) now specifies HMAC signing of the state parameter using `hmac.new(key, state.encode(), hashlib.sha256)` with `TOKEN_ENCRYPTION_KEY` as the signing key. The HMAC signature is stored in the cookie (not the raw state), and the callback recomputes the HMAC from the received `state` query parameter and compares using `hmac.compare_digest()`. This is a sound approach:

- Uses a key the app already requires (`TOKEN_ENCRYPTION_KEY`), avoiding a new env var.
- `hmac.compare_digest()` prevents timing attacks.
- 10-minute max-age on the cookie limits the replay window.
- The plan explicitly notes that app restarts do not break validation because the key comes from the environment.

Test coverage is adequate: `test_sign_and_verify_state`, `test_tampered_state_cookie_rejected`, `test_callback_rejects_tampered_cookie`.

**Status: Adequately fixed.**

---

### R1-2. No CSRF on POST /oauth/disconnect (was Critical) -- RESOLVED

The revised plan (Section 4) adds CSRF protection to the disconnect endpoint using an HMAC-based token scheme. A random `session_nonce` is stored in a cookie when the settings page renders, and the CSRF token is `hmac(key, "disconnect:" + session_nonce)`. The POST handler recomputes and compares.

Test coverage is adequate: `test_disconnect_rejects_missing_csrf_token`, `test_disconnect_rejects_invalid_csrf_token`, `test_disconnect_deletes_tokens` (with valid token).

**Status: Adequately fixed.**

---

### R1-3. Token refresh race condition (was Major) -- RESOLVED

The revised plan (Section 8) adds a `threading.Lock` (`_refresh_lock`) around the refresh operation. After acquiring the lock, the code re-checks token expiry to avoid redundant refreshes. The plan correctly notes this is sufficient because the app runs as a single process.

**Status: Adequately fixed.**

---

### R1-4. No redirect URI validation (was Major) -- RESOLVED

The revised plan (Section 1) adds `validate_redirect_uri()` called at startup. It parses the URI, rejects any path that is not `/oauth/callback`, and logs a warning for non-localhost hosts. This prevents silent misconfiguration.

Test coverage: `test_redirect_uri_path_validation`.

**Status: Adequately fixed.**

---

### R1-5. No Fernet key validation at startup (was Major) -- RESOLVED

The revised plan (Section 1) adds a Pydantic `field_validator` on `token_encryption_key` that attempts `Fernet(v.encode())` during settings instantiation. Empty values are allowed (disabling OAuth). Invalid values fail fast with a clear error message.

Test coverage: `test_fernet_key_validated_at_startup`, `test_fernet_key_empty_disables_oauth`.

**Status: Adequately fixed.**

---

### R1-6. Error responses leaking client_secret (was Major) -- RESOLVED

The revised plan (Section 9) adds explicit exception sanitization. All httpx exceptions are caught and re-raised using `from None` to suppress the original exception chain (which contains the httpx request object with sensitive data). Only HTTP status codes are logged.

The code example is well-structured: catches `HTTPStatusError` and `HTTPError` separately, logs only status codes, and raises a sanitized `OAuthTokenExchangeError`.

Test coverage: `test_exception_sanitization_no_secret_in_error`.

**Status: Adequately fixed.**

---

## Status of Round 1 Minor/Info Findings

### R1-7. No unique constraint on `provider` (was Minor) -- RESOLVED

The model definition now includes `unique=True` on the `provider` column (Section 2, line: `provider: str = Column(String, nullable=False, default="linkedin", unique=True)`).

### R1-8. No rate limiting on OAuth endpoints (was Minor) -- ACKNOWLEDGED

Not explicitly addressed in the revision, but the CSRF protection on disconnect and the HMAC-signed state on authorize significantly reduce the attack surface that motivated this finding. Acceptable for a single-user self-hosted app.

### R1-9. DB file permissions (was Minor) -- NOT ADDRESSED

Still relies on system-level permissions. Acceptable given the defense-in-depth from Fernet encryption.

### R1-10. No token compromise detection (was Minor) -- NOT ADDRESSED

Acceptable for the current scope. Can be revisited in the data sync plan.

### R1-11. App restart mid-flow (was Minor) -- RESOLVED

Section 4 explicitly documents that HMAC signing survives app restarts because the key is from the environment.

### R1-12. HTTP default for redirect URI (was Info) -- RESOLVED

Section 1 and the env var table now include guidance that production must use HTTPS. `.env.example` update includes this note.

### R1-13. Key rotation test missing (was Info) -- RESOLVED

Section 7 now documents that `decrypt_token` catches `InvalidToken` and treats it as "not connected." Test `test_decrypt_with_wrong_key_returns_none` covers this.

### R1-14. Scope parsing fragility (was Info) -- NOT ADDRESSED

Still uses space-separated string. Acceptable; this is standard OAuth 2.0 scope representation.

---

## New Findings from Round 2

### 15. Reusing TOKEN_ENCRYPTION_KEY for HMAC signing conflates two security functions

**Severity: Minor**

The plan uses `TOKEN_ENCRYPTION_KEY` (a Fernet key) for three distinct purposes:

1. Fernet encryption of tokens at rest
2. HMAC signing of the OAuth state parameter
3. HMAC signing of the disconnect CSRF token

Fernet keys are 32 bytes of key material (16 bytes signing + 16 bytes encryption, base64-encoded). Using the raw Fernet key string as an HMAC key works, but it conflates encryption and authentication functions. If the HMAC usage leaks any information about the key (unlikely with SHA-256, but a defense-in-depth concern), it could theoretically weaken the Fernet encryption.

Best practice is to derive separate keys for separate purposes using HKDF or at minimum to use different HMAC prefixes (e.g., `hmac(key, "state:" + value)` vs `hmac(key, "csrf:" + value)`). The plan does use `"disconnect:"` as a prefix for the CSRF token HMAC, which provides some domain separation, but the state signing uses the raw value without a prefix.

**Recommendation:** Add a prefix to the state HMAC: `hmac(key, "oauth_state:" + state)`. This costs nothing and provides domain separation between the two HMAC usages. No new env var needed.

---

### 16. CSRF nonce cookie for disconnect lacks HttpOnly and SameSite attributes

**Severity: Minor**

Section 4 describes storing a `session_nonce` in a cookie when the settings page is rendered, used to compute the disconnect CSRF token. The plan specifies `HttpOnly` and `SameSite=Lax` for the `oauth_state` cookie but does not specify these attributes for the `session_nonce` cookie.

Without `HttpOnly`, a cross-site script (XSS) could read the nonce and compute a valid CSRF token (assuming the attacker also knows the signing key, which is unlikely, but defense-in-depth applies). Without `SameSite=Lax`, the cookie could be sent on cross-origin requests in older browsers.

**Recommendation:** Explicitly specify `HttpOnly=True`, `SameSite=Lax`, and a reasonable `max-age` (e.g., 1 hour) for the `session_nonce` cookie. Add this to the implementation spec in Section 4.

---

### 17. No test for concurrent token refresh (threading.Lock validation)

**Severity: Info**

The plan adds `threading.Lock` for the refresh race condition (R1-3) but the test plan does not include a concurrency test that exercises the lock. For example, a test that spawns two threads both calling `get_valid_access_token()` with an expired token and verifies that only one refresh HTTP call is made.

**Recommendation:** Add a concurrency test using `threading.Thread` or `concurrent.futures` to verify the lock prevents double-refresh. This is an Info-level suggestion since the locking pattern is straightforward and well-understood.

---

## Summary

| Severity | Count | Findings |
|---|---|---|
| Critical | 0 | -- |
| Major | 0 | -- |
| Minor | 2 | #15 (key reuse across HMAC domains), #16 (nonce cookie attributes) |
| Info | 1 | #17 (no concurrency test for refresh lock) |

All six Critical and Major findings from Round 1 have been resolved with appropriate implementations, test coverage, and documentation. The plan is ready for implementation. The two Minor findings above are improvements to adopt during implementation but do not block approval.
