"""Shared client for Google APIs that use the same OAuth credentials.

Google Ads needs a developer token and its own endpoint; GA4 and Tag Manager
do not. What they share is the OAuth client and refresh token, so the token
provider is reused and only the transport differs.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from .auth import TokenProvider
from .config import Config, ConfigError, load_config


class GoogleApiError(RuntimeError):
    """Raised when a Google API rejects a request."""


def _explain(response: httpx.Response, url: str) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"{response.status_code} calling {url}: {response.text[:400]}"

    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    message = error.get("message", response.text[:300])
    status = error.get("status", "")
    parts = [f"Google API error {response.status_code} {status}: {message}"]

    blob = f"{message} {status}".lower()
    hints = [
        ("insufficient authentication scopes",
         "The refresh token was minted without this API's scope. Re-mint it "
         "including every scope you need — scopes are fixed at issue time."),
        ("has not been used in project",
         "The API is not enabled in the Cloud project. Enable it, then wait a "
         "few minutes for the change to propagate."),
        ("permission_denied",
         "The authorised Google user lacks access to this property or "
         "container. The API grants no permissions of its own."),
        ("not found",
         "Check the ID. GA4 wants the numeric property ID, and Tag Manager "
         "wants the numeric container ID from the URL, not the GTM-XXXX "
         "public ID."),
    ]
    for needle, hint in hints:
        if needle in blob:
            parts.append(f"Fix: {hint}")
            break
    parts.append(f"URL: {url}")
    return "\n\n".join(parts)


class GoogleApiClient:
    """Minimal authenticated JSON client shared by the GA4 and GTM modules."""

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or load_config()
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0))
        self._tokens = TokenProvider(self._config, self._http)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {await self._tokens.access_token()}",
            "Content-Type": "application/json",
        }

    async def get(self, url: str, params: dict | None = None) -> dict[str, Any]:
        try:
            r = await self._http.get(url, headers=await self._headers(), params=params)
        except httpx.HTTPError as exc:
            raise GoogleApiError(f"Could not reach {url}: {exc}") from exc
        if r.status_code != 200:
            raise GoogleApiError(_explain(r, url))
        return r.json()

    async def post(self, url: str, body: dict) -> dict[str, Any]:
        try:
            r = await self._http.post(url, headers=await self._headers(), json=body)
        except httpx.HTTPError as exc:
            raise GoogleApiError(f"Could not reach {url}: {exc}") from exc
        if r.status_code != 200:
            raise GoogleApiError(_explain(r, url))
        return r.json()

    async def scopes(self) -> list[str]:
        """Scopes actually carried by the refresh token in use."""
        token = await self._tokens.access_token()
        r = await self._http.get("https://oauth2.googleapis.com/tokeninfo",
                                 params={"access_token": token})
        if r.status_code != 200:
            raise GoogleApiError(f"Could not inspect token: {r.text[:200]}")
        return r.json().get("scope", "").split()


def required_env(name: str, hint: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is not set. {hint}")
    return value
