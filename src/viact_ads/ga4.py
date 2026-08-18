"""Google Analytics 4 — reporting (Data API) and configuration (Admin API)."""

from __future__ import annotations

import re
from typing import Any

from .google_api import GoogleApiClient, required_env

DATA = "https://analyticsdata.googleapis.com/v1beta"
ADMIN = "https://analyticsadmin.googleapis.com/v1beta"

PRESETS = {
    "TODAY": ("today", "today"),
    "YESTERDAY": ("yesterday", "yesterday"),
    "LAST_7_DAYS": ("7daysAgo", "yesterday"),
    "LAST_14_DAYS": ("14daysAgo", "yesterday"),
    "LAST_28_DAYS": ("28daysAgo", "yesterday"),
    "LAST_30_DAYS": ("30daysAgo", "yesterday"),
    "LAST_90_DAYS": ("90daysAgo", "yesterday"),
}

_EXPLICIT = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})\s*(?:,|to|\.\.)\s*(\d{4}-\d{2}-\d{2})\s*$", re.I)


def date_range(value: str) -> dict[str, str]:
    """Accept a preset or 'YYYY-MM-DD,YYYY-MM-DD'."""
    text = (value or "").strip()
    upper = text.upper().replace(" ", "_")
    if upper in PRESETS:
        start, end = PRESETS[upper]
        return {"startDate": start, "endDate": end}
    match = _EXPLICIT.match(text)
    if match:
        start, end = match.group(1), match.group(2)
        if start > end:
            raise ValueError(f"date_range start {start} is after end {end}.")
        return {"startDate": start, "endDate": end}
    raise ValueError(
        f"Unrecognised date_range {value!r}. Use a preset "
        f"({', '.join(sorted(PRESETS))}) or 'YYYY-MM-DD,YYYY-MM-DD'."
    )


def property_id(explicit: str | None = None) -> str:
    raw = explicit or required_env(
        "GA4_PROPERTY_ID",
        "Find it in GA4 under Admin > Property details, top right. Digits only.")
    digits = re.sub(r"[^0-9]", "", str(raw))
    if not digits:
        raise ValueError(f"GA4 property ID must be numeric, got {raw!r}.")
    return digits


def flatten_report(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn GA4's parallel header/row arrays into plain dicts."""
    dim_names = [h.get("name") for h in payload.get("dimensionHeaders", [])]
    met_names = [h.get("name") for h in payload.get("metricHeaders", [])]
    rows = []
    for row in payload.get("rows", []):
        record: dict[str, Any] = {}
        for name, cell in zip(dim_names, row.get("dimensionValues", [])):
            record[name] = cell.get("value")
        for name, cell in zip(met_names, row.get("metricValues", [])):
            raw = cell.get("value")
            try:
                record[name] = float(raw) if "." in str(raw) else int(raw)
            except (TypeError, ValueError):
                record[name] = raw
        rows.append(record)
    return rows


class GA4Client:
    def __init__(self, api: GoogleApiClient) -> None:
        self._api = api

    async def run_report(
        self,
        dimensions: list[str],
        metrics: list[str],
        date_range_value: str = "LAST_30_DAYS",
        prop: str | None = None,
        limit: int = 250,
        order_by_metric: str | None = None,
        dimension_filter: dict | None = None,
    ) -> dict[str, Any]:
        pid = property_id(prop)
        body: dict[str, Any] = {
            "dateRanges": [date_range(date_range_value)],
            "dimensions": [{"name": d} for d in dimensions],
            "metrics": [{"name": m} for m in metrics],
            "limit": int(limit),
        }
        if order_by_metric:
            body["orderBys"] = [
                {"metric": {"metricName": order_by_metric}, "desc": True}]
        if dimension_filter:
            body["dimensionFilter"] = dimension_filter
        payload = await self._api.post(f"{DATA}/properties/{pid}:runReport", body)
        return {
            "property_id": pid,
            "date_range": date_range(date_range_value),
            "row_count": payload.get("rowCount", 0),
            "rows": flatten_report(payload),
        }

    async def key_events(self, prop: str | None = None) -> dict[str, Any]:
        """Key events — what GA4 counts as a conversion and exports to Google Ads."""
        pid = property_id(prop)
        payload = await self._api.get(f"{ADMIN}/properties/{pid}/keyEvents",
                                      {"pageSize": 200})
        events = [{
            "name": e.get("eventName"),
            "resource_name": e.get("name"),
            "counting": e.get("countingMethod"),
            "created": e.get("createTime"),
            "deletable": e.get("deletable"),
            "custom": e.get("custom"),
        } for e in payload.get("keyEvents", [])]
        return {"property_id": pid, "count": len(events), "key_events": events}

    async def property_details(self, prop: str | None = None) -> dict[str, Any]:
        pid = property_id(prop)
        return await self._api.get(f"{ADMIN}/properties/{pid}")

    async def data_streams(self, prop: str | None = None) -> dict[str, Any]:
        pid = property_id(prop)
        payload = await self._api.get(f"{ADMIN}/properties/{pid}/dataStreams",
                                      {"pageSize": 200})
        streams = [{
            "name": s.get("displayName"),
            "type": s.get("type"),
            # The measurement ID lives here — the G-XXXX used on the website.
            "measurement_id": (s.get("webStreamData") or {}).get("measurementId"),
            "default_uri": (s.get("webStreamData") or {}).get("defaultUri"),
        } for s in payload.get("dataStreams", [])]
        return {"property_id": pid, "count": len(streams), "data_streams": streams}

    async def google_ads_links(self, prop: str | None = None) -> dict[str, Any]:
        """Which Google Ads accounts this property exports conversions to."""
        pid = property_id(prop)
        payload = await self._api.get(f"{ADMIN}/properties/{pid}/googleAdsLinks",
                                      {"pageSize": 50})
        links = [{
            "customer_id": l.get("customerId"),
            "ads_personalization": l.get("adsPersonalizationEnabled"),
            "creator": l.get("creatorEmailAddress"),
        } for l in payload.get("googleAdsLinks", [])]
        return {"property_id": pid, "count": len(links), "google_ads_links": links}
