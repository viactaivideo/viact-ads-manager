"""OAuth2 access-token minting.

The refresh token is long-lived; access tokens last ~1 hour. This exchanges one
for the other and caches the result until shortly before it expires.
"""

from __future__ import annotations

import asyncio
import time

import httpx

from .config import Config

TOKEN_URL = "https://oauth2.googleapis.com/token"

# Refresh a little early so a token cannot expire mid-request.
EXPIRY_SKEW_SECONDS = 60


class AuthError(RuntimeError):
    """Raised when the refresh token cannot be exchanged for an access token."""


class TokenProvider:
    def __init__(self, config: Config, http: httpx.AsyncClient) -> None:
        self._config = config
        self._http = http
        self._access_token: str | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    async def access_token(self) -> str:
        # Fast path: a valid cached token, no lock contention.
        if self._access_token and time.monotonic() < self._expires_at:
            return self._access_token

        async with self._lock:
            # Another coroutine may have refreshed while we waited.
            if self._access_token and time.monotonic() < self._expires_at:
                return self._access_token
            return await self._refresh()

    async def _refresh(self) -> str:
        try:
            response = await self._http.post(
                TOKEN_URL,
                data={
                    "client_id": self._config.client_id,
                    "client_secret": self._config.client_secret,
                    "refresh_token": self._config.refresh_token,
                    "grant_type": "refresh_token",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )
        except httpx.HTTPError as exc:
            raise AuthError(f"Could not reach Google's OAuth endpoint: {exc}") from exc

        if response.status_code != 200:
            raise AuthError(_explain_token_error(response))

        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise AuthError(f"OAuth response contained no access_token: {payload}")

        expires_in = int(payload.get("expires_in", 3600))
        self._access_token = token
        self._expires_at = time.monotonic() + max(expires_in - EXPIRY_SKEW_SECONDS, 0)
        return token


def _explain_token_error(response: httpx.Response) -> str:
    """Turn Google's terse OAuth errors into something actionable."""
    try:
        payload = response.json()
    except ValueError:
        payload = {}

    code = payload.get("error", "")
    description = payload.get("error_description", response.text[:400])
    base = f"OAuth token refresh failed ({response.status_code} {code}): {description}"

    hints = {
        "invalid_grant": (
            "The refresh token is expired, revoked, or was issued by a different "
            "OAuth client. Re-run `uv run python scripts/get_refresh_token.py` and "
            "update GOOGLE_ADS_REFRESH_TOKEN. Note: tokens from an OAuth consent "
            "screen still in 'Testing' mode expire after 7 days — publish the app "
            "to stop that."
        ),
        "invalid_client": (
            "GOOGLE_ADS_CLIENT_ID / GOOGLE_ADS_CLIENT_SECRET do not match a real "
            "OAuth client. Re-copy them from Google Cloud Console > Credentials."
        ),
        "unauthorized_client": (
            "This OAuth client is not allowed to use the refresh_token grant. "
            "Make sure the client was created as an 'Desktop app' type."
        ),
    }
    hint = hints.get(code)
    return f"{base}\n\n{hint}" if hint else base
