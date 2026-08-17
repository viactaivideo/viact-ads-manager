"""Thin async client for the Google Ads REST API.

Talks to googleads.googleapis.com directly. No vendor middleman, and no
protobuf client library — GAQL goes in, flat rows come out.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from .auth import TokenProvider
from .config import Config

_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


class GoogleAdsError(RuntimeError):
    """Raised when the Google Ads API rejects a request."""


def _to_snake(name: str) -> str:
    """costMicros -> cost_micros. REST responses are camelCase; GAQL is snake."""
    return _CAMEL_BOUNDARY.sub("_", name).lower()


def _flatten(node: Any, prefix: str = "") -> dict[str, Any]:
    """Collapse a nested GoogleAdsRow into dotted snake_case keys.

    {"metrics": {"costMicros": "12"}} -> {"metrics.cost_micros": "12"}
    Lists are kept intact rather than exploded, so repeated fields survive.
    """
    flat: dict[str, Any] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{prefix}.{_to_snake(key)}" if prefix else _to_snake(key)
            if isinstance(value, dict):
                flat.update(_flatten(value, path))
            else:
                flat[path] = value
    elif prefix:
        flat[prefix] = node
    return flat


# Money fields Google reports in micros *without* naming them so. Averaged and
# derived metrics all fall in here, which makes them easy to misread by a
# factor of a million.
IMPLICIT_MICROS = frozenset(
    {
        "metrics.average_cpc",
        "metrics.average_cpm",
        "metrics.average_cpv",
        "metrics.average_cpe",
        "metrics.average_cost",
        "metrics.cost_per_conversion",
        "metrics.cost_per_all_conversions",
        "metrics.cost_per_current_model_attributed_conversion",
    }
)


def _add_currency_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Google reports money in micros. Add or convert to human-scale values."""
    for key in list(row):
        explicit = key.endswith("_micros")
        if not explicit and key not in IMPLICIT_MICROS:
            continue
        try:
            value = float(row[key])
        except (TypeError, ValueError):
            continue
        if explicit:
            # Keep the raw field and add a companion: metrics.cost_micros
            # stays, metrics.cost appears next to it.
            row[key.removesuffix("_micros")] = round(value / 1_000_000, 4)
        else:
            # Nothing signals micros in the name, so convert in place rather
            # than leaving a value that reads as a million times too large.
            row[key] = round(value / 1_000_000, 4)
    return row


class GoogleAdsClient:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0))
        self._tokens = TokenProvider(config, self._http)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _headers(self, login_customer_id: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {await self._tokens.access_token()}",
            "developer-token": self._config.developer_token,
            "Content-Type": "application/json",
        }
        # Identifies the manager account authorising the call. Required whenever
        # the queried account is reached *through* an MCC.
        effective = login_customer_id or self._config.login_customer_id
        if effective:
            headers["login-customer-id"] = effective
        return headers

    async def list_accessible_customers(self) -> list[str]:
        """Account IDs these credentials can reach directly (usually just the MCC)."""
        url = f"{self._config.endpoint}/customers:listAccessibleCustomers"
        try:
            response = await self._http.get(url, headers=await self._headers())
        except httpx.HTTPError as exc:
            raise GoogleAdsError(f"Could not reach the Google Ads API: {exc}") from exc

        if response.status_code != 200:
            raise GoogleAdsError(_explain_api_error(response))

        resource_names = response.json().get("resourceNames", [])
        return [name.split("/")[-1] for name in resource_names]

    async def search(
        self,
        query: str,
        customer_id: str | None = None,
        login_customer_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run a GAQL query via searchStream and return flattened rows."""
        target = self._config.resolve_customer_id(customer_id)
        url = f"{self._config.endpoint}/customers/{target}/googleAds:searchStream"

        try:
            response = await self._http.post(
                url,
                headers=await self._headers(login_customer_id),
                json={"query": query},
            )
        except httpx.HTTPError as exc:
            raise GoogleAdsError(f"Could not reach the Google Ads API: {exc}") from exc

        if response.status_code != 200:
            raise GoogleAdsError(_explain_api_error(response, query=query))

        payload = response.json()
        # searchStream returns an array of batches, each holding a `results` list.
        if isinstance(payload, dict):
            payload = [payload]

        rows: list[dict[str, Any]] = []
        for batch in payload:
            for result in batch.get("results", []):
                rows.append(_add_currency_fields(_flatten(result)))
        return rows


    async def mutate(
        self,
        service: str,
        operations: list[dict[str, Any]],
        customer_id: str | None = None,
        validate_only: bool = True,
        login_customer_id: str | None = None,
    ) -> dict[str, Any]:
        """Send operations to a mutate endpoint.

        `validate_only=True` asks Google to check the request and change
        nothing, which is what makes a preview trustworthy: the same payload
        that gets validated is the one later applied.
        """
        from .mutations import SERVICES

        if service not in SERVICES:
            raise GoogleAdsError(f"Unknown mutate service {service!r}.")
        target = self._config.resolve_customer_id(customer_id)
        url = (
            f"{self._config.endpoint}/customers/{target}"
            f"/{SERVICES[service]}:mutate"
        )
        body = {
            "operations": operations,
            "validateOnly": bool(validate_only),
            # Without this a single bad row would reject the whole batch.
            "partialFailure": not validate_only,
        }
        return await self._post(url, body, login_customer_id)

    async def upload_click_conversions(
        self,
        conversions: list[dict[str, Any]],
        customer_id: str | None = None,
        validate_only: bool = True,
        login_customer_id: str | None = None,
    ) -> dict[str, Any]:
        target = self._config.resolve_customer_id(customer_id)
        url = f"{self._config.endpoint}/customers/{target}:uploadClickConversions"
        body = {
            "conversions": conversions,
            "validateOnly": bool(validate_only),
            "partialFailure": not validate_only,
        }
        return await self._post(url, body, login_customer_id)

    async def _post(
        self, url: str, body: dict[str, Any], login_customer_id: str | None
    ) -> dict[str, Any]:
        try:
            response = await self._http.post(
                url, headers=await self._headers(login_customer_id), json=body
            )
        except httpx.HTTPError as exc:
            raise GoogleAdsError(f"Could not reach the Google Ads API: {exc}") from exc

        if response.status_code != 200:
            raise GoogleAdsError(_explain_api_error(response))

        payload = response.json()
        # partialFailure means a 200 can still carry per-row rejections.
        failure = payload.get("partialFailureError")
        if failure:
            raise GoogleAdsError(
                "Google rejected some operations:\n"
                + _describe_partial_failure(failure)
            )
        return payload


def _describe_partial_failure(failure: dict[str, Any]) -> str:
    reasons = []
    for detail in failure.get("details", []):
        for item in detail.get("errors", []):
            code = item.get("errorCode", {})
            label = next(iter(code.values()), "") if isinstance(code, dict) else ""
            index = ""
            for element in item.get("location", {}).get("fieldPathElements", []):
                if element.get("fieldName") == "operations":
                    index = f"operation {element.get('index', '?')}: "
            reasons.append(f"  - {index}{label}: {item.get('message', '')}".rstrip(": "))
    return "\n".join(reasons) or f"  - {failure.get('message', 'unknown error')}"


def _explain_api_error(response: httpx.Response, query: str | None = None) -> str:
    """Surface Google's nested error detail, plus a fix for the common cases."""
    try:
        payload = response.json()
    except ValueError:
        return f"Google Ads API error {response.status_code}: {response.text[:600]}"

    if isinstance(payload, list) and payload:
        payload = payload[0]

    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    message = error.get("message", response.text[:400])
    status = error.get("status", "")

    # The useful part lives in details[].errors[].errorCode.
    reasons: list[str] = []
    for detail in error.get("details", []):
        for item in detail.get("errors", []):
            code = item.get("errorCode", {})
            label = next(iter(code.values()), "") if isinstance(code, dict) else ""
            text = item.get("message", "")
            reasons.append(f"{label}: {text}".strip(": "))

    parts = [f"Google Ads API error {response.status_code} {status}: {message}"]
    if reasons:
        parts.append("Details:\n  - " + "\n  - ".join(reasons))

    blob = " ".join([message, status, *reasons])
    hint = _hint_for(blob)
    if hint:
        parts.append(f"Fix: {hint}")
    if query:
        parts.append(f"Query was:\n{query.strip()}")
    return "\n\n".join(parts)


def _hint_for(blob: str) -> str | None:
    checks = [
        (
            "DEVELOPER_TOKEN_NOT_APPROVED",
            "Your developer token only has Test Account access. Apply for Basic "
            "access in the MCC under Tools > Setup > API Center — production "
            "accounts stay unreadable until that is approved.",
        ),
        (
            "DEVELOPER_TOKEN_PROHIBITED",
            "This developer token is not permitted to use the API. Check the "
            "token's status in the MCC's API Center.",
        ),
        (
            "USER_PERMISSION_DENIED",
            "The authenticated Google user cannot access this customer ID. Either "
            "the account is not linked under your MCC, or GOOGLE_ADS_LOGIN_CUSTOMER_ID "
            "is not the manager that owns it.",
        ),
        (
            "CUSTOMER_NOT_ENABLED",
            "That account is cancelled or not fully signed up in Google Ads.",
        ),
        (
            "NOT_ADS_USER",
            "The Google account you authorised has no Google Ads profile. Re-run "
            "the refresh-token script and sign in with an account that does.",
        ),
        (
            "QUERY_ERROR",
            "The GAQL is malformed. Field names are snake_case, string literals "
            "need single quotes, and metrics cannot be filtered in the SELECT list.",
        ),
        (
            "RESOURCE_EXHAUSTED",
            "You hit a rate or daily-operation limit. Basic access allows 15,000 "
            "operations/day — wait and retry, or request Standard access.",
        ),
        (
            "authentication credential",
            "The access token was rejected. Confirm the OAuth client and refresh "
            "token belong together and were issued for the Google Ads scope.",
        ),
    ]
    for needle, hint in checks:
        if needle.lower() in blob.lower():
            return hint
    return None
