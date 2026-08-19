"""Pipedrive API v2 client, used as the CRM side of the offline conversion bridge.

Only the pieces the bridge needs: reading deals, resolving custom field keys,
and pulling the person email that Google matches a conversion back to.

Two Pipedrive quirks drive the shape of this module:

* v2 authenticates with an ``x-api-token`` header. The old ``?api_token=``
  query parameter is rejected, so the token must never appear in a URL.
* Every custom field is keyed by a random 40-character hash that differs per
  Pipedrive account, so a field like "GCLID" cannot be hardcoded. It has to be
  looked up by name at runtime — see :meth:`PipedriveClient.field_key`.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx

from .config import load_dotenv

DEFAULT_HOST = "https://api.pipedrive.com"
FIELD_HASH = re.compile(r"^[0-9a-f]{40}$")


class PipedriveError(RuntimeError):
    """Raised when Pipedrive rejects a request or the response is unusable."""


def api_token(explicit: str | None = None) -> str:
    """Resolve the API token, preferring an explicit argument."""
    load_dotenv()  # same fallback the Google Ads credentials get
    token = (explicit or os.environ.get("PIPEDRIVE_API_TOKEN") or "").strip()
    if not token:
        raise PipedriveError(
            "PIPEDRIVE_API_TOKEN is not set. Create one in Pipedrive under "
            "Settings > Personal preferences > API, then add it to the "
            "environment. Never pass it in a URL: API v2 requires the "
            "x-api-token header."
        )
    return token


def api_host(explicit: str | None = None) -> str:
    """Company-specific host, e.g. https://viact.pipedrive.com, or the default."""
    load_dotenv()
    host = (explicit or os.environ.get("PIPEDRIVE_HOST") or DEFAULT_HOST).strip()
    return host.rstrip("/")


def normalize_email(value: str) -> str:
    """Lowercase and trim, and strip Gmail dot/plus aliasing.

    Google hashes the normalised address, so a mismatch in normalisation is a
    silent match failure rather than an error.
    """
    email = str(value or "").strip().lower()
    if "@" not in email:
        raise PipedriveError(f"Not an email address: {value!r}")
    local, _, domain = email.partition("@")
    if domain in ("gmail.com", "googlemail.com"):
        local = local.split("+", 1)[0].replace(".", "")
    return f"{local}@{domain}"


def hash_email(value: str) -> str:
    """SHA-256 of the normalised address, hex encoded, as Google expects."""
    return hashlib.sha256(normalize_email(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Deal:
    """The subset of a Pipedrive deal the bridge cares about."""

    id: int
    title: str
    status: str
    stage_id: int | None
    value: float | None
    currency: str | None
    add_time: str | None
    won_time: str | None
    update_time: str | None
    email: str | None
    gclid: str | None

    def conversion_time(self) -> str | None:
        """When the conversion happened. Won time if present, else created."""
        return self.won_time or self.add_time


class PipedriveClient:
    def __init__(
        self,
        token: str | None = None,
        host: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._token = api_token(token)
        self._host = api_host(host)
        self._http = httpx.AsyncClient(timeout=30.0, transport=transport)
        self._field_cache: dict[str, str] | None = None

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._host}{path}"
        try:
            response = await self._http.get(
                url,
                headers={"x-api-token": self._token, "Accept": "application/json"},
                params=params or {},
            )
        except httpx.HTTPError as exc:
            raise PipedriveError(f"Could not reach Pipedrive: {exc}") from exc

        if response.status_code == 401:
            raise PipedriveError(
                "Pipedrive rejected the API token (401). Check PIPEDRIVE_API_TOKEN "
                "and that the user it belongs to still has access."
            )
        if response.status_code == 429:
            raise PipedriveError(
                "Pipedrive rate limit reached (429). The daily token budget is "
                "shared across the whole company account and resets every 24 "
                "hours. Reduce the page size or run the bridge less often."
            )
        if response.status_code != 200:
            raise PipedriveError(
                f"Pipedrive returned {response.status_code} for {path}: "
                f"{response.text[:300]}"
            )
        payload = response.json()
        if payload.get("success") is False:
            raise PipedriveError(
                f"Pipedrive reported failure for {path}: {payload.get('error')}"
            )
        return payload

    # ------------------------------------------------------------------
    # Custom fields
    # ------------------------------------------------------------------
    async def deal_fields(self) -> dict[str, str]:
        """Map lowercased field name -> 40-character API key.

        Pipedrive gives every custom field a random hash key that differs per
        account, so the bridge resolves the key by name once and caches it.
        """
        if self._field_cache is not None:
            return self._field_cache
        payload = await self._get("/v1/dealFields")
        mapping: dict[str, str] = {}
        for field in payload.get("data") or []:
            name = str(field.get("name") or "").strip().lower()
            key = str(field.get("key") or "")
            if name and key:
                mapping[name] = key
        self._field_cache = mapping
        return mapping

    async def field_key(self, name: str) -> str | None:
        """Resolve a custom field name to its hash key, or None if absent."""
        fields = await self.deal_fields()
        return fields.get(str(name).strip().lower())

    # ------------------------------------------------------------------
    # Deals
    # ------------------------------------------------------------------
    async def deals(
        self,
        status: str | None = "won",
        updated_since: str | None = None,
        limit: int = 500,
        gclid_field: str | None = None,
        resolve_emails: bool = True,
    ) -> list[Deal]:
        """Read deals, newest first, resolving email and any GCLID field.

        ``updated_since`` takes an RFC3339 timestamp. Pipedrive returns person
        email inline on v2 deals, so no extra call per deal is needed.
        """
        gclid_key = None
        if gclid_field:
            gclid_key = (
                gclid_field
                if FIELD_HASH.match(gclid_field)
                else await self.field_key(gclid_field)
            )

        params: dict[str, Any] = {"limit": min(int(limit), 500), "sort_by": "update_time",
                                  "sort_direction": "desc"}
        if status:
            params["status"] = status
        if updated_since:
            params["updated_since"] = updated_since

        payload = await self._get("/api/v2/deals", params)
        rows = payload.get("data") or []

        # v2 gives person_id as an integer, so the email needs a second lookup.
        lookup: dict[int, str] = {}
        if resolve_emails and any(isinstance(r.get("person_id"), int) for r in rows):
            lookup = await self.person_emails()

        out: list[Deal] = []
        for row in rows:
            out.append(
                Deal(
                    id=int(row.get("id", 0)),
                    title=str(row.get("title") or ""),
                    status=str(row.get("status") or ""),
                    stage_id=row.get("stage_id"),
                    value=_as_float(row.get("value")),
                    currency=row.get("currency"),
                    add_time=row.get("add_time"),
                    won_time=row.get("won_time"),
                    update_time=row.get("update_time"),
                    email=_first_email(row) or lookup.get(_person_id(row)),
                    gclid=_custom(row, gclid_key),
                )
            )
        return out


    # ------------------------------------------------------------------
    # People
    # ------------------------------------------------------------------
    async def person_emails(self) -> dict[int, str]:
        """Map person id -> primary email.

        API v2 returns ``person_id`` on a deal as a bare integer; unlike v1 it
        does not inline the person's email. Google matches an offline
        conversion on that email, so it has to be fetched separately and
        joined on. Paged rather than fetched per deal: one pass over the
        address book costs a handful of requests instead of one per deal.
        """
        emails: dict[int, str] = {}
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"limit": 500}
            if cursor:
                params["cursor"] = cursor
            payload = await self._get("/api/v2/persons", params)
            rows = payload.get("data") or []
            for row in rows:
                pid = row.get("id")
                email = _first_email(row)
                if pid is not None and email:
                    emails[int(pid)] = email
            cursor = (payload.get("additional_data") or {}).get("next_cursor")
            if not cursor or not rows:
                break
        return emails

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------
    async def describe(self, sample: int = 20) -> dict[str, Any]:
        """Report the *shape* of this account's deals, never their contents.

        Deal titles carry client and tender names, so a diagnostic that dumps
        rows is unusable anywhere the output might be read by someone outside
        the company. This returns key names, value types and counts only, so
        it is safe to print in a CI log.
        """
        payload = await self._get("/api/v2/deals", {"limit": min(int(sample), 500)})
        rows = payload.get("data") or []
        fields = await self.deal_fields()

        interesting = sorted(
            name for name in fields
            if any(word in name for word in ("gclid", "click", "utm", "email", "source", "campaign"))
        )
        first = rows[0] if rows else {}
        return {
            "deals_sampled": len(rows),
            "deal_keys": sorted(first.keys()),
            "person_id_type": type(first.get("person_id")).__name__,
            "custom_fields_present": sum(1 for r in rows if r.get("custom_fields")),
            "with_person_id": sum(1 for r in rows if r.get("person_id")),
            "email_found_by_current_code": sum(1 for r in rows if _first_email(r)),
            "deal_field_names_worth_checking": interesting,
            "total_deal_fields": len(fields),
        }


def _person_id(row: dict[str, Any]) -> int:
    """The deal's person id, whether v2 gave an integer or v1 gave an object."""
    person = row.get("person_id")
    if isinstance(person, dict):
        person = person.get("value") or person.get("id")
    try:
        return int(person)
    except (TypeError, ValueError):
        return -1


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _custom(row: dict[str, Any], key: str | None) -> str | None:
    """Read a custom field, which v2 nests under custom_fields."""
    if not key:
        return None
    custom = row.get("custom_fields") or {}
    value = custom.get(key, row.get(key))
    if isinstance(value, dict):
        value = value.get("value")
    text = str(value).strip() if value is not None else ""
    return text or None


def _first_email(row: dict[str, Any]) -> str | None:
    """Primary email from a person row, or from a deal that inlines one."""
    person = row.get("person_id")
    if not isinstance(person, dict) and (row.get("emails") or row.get("email")):
        person = row  # a person row from /api/v2/persons
    if isinstance(person, dict):
        emails = person.get("emails") or person.get("email") or []
        if isinstance(emails, str):
            return emails.strip() or None
        for entry in emails:
            if isinstance(entry, dict):
                if entry.get("primary") and entry.get("value"):
                    return str(entry["value"]).strip()
            elif entry:
                return str(entry).strip()
        for entry in emails:
            if isinstance(entry, dict) and entry.get("value"):
                return str(entry["value"]).strip()
    email = row.get("person_email") or row.get("email")
    if isinstance(email, str) and email.strip():
        return email.strip()
    return None
