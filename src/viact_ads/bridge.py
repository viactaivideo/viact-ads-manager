"""Pipedrive -> Google Ads offline conversion bridge.

Reads deals from Pipedrive, keeps the ones Google will actually accept, and
uploads them as offline conversions so Smart Bidding learns which leads the
sales team valued rather than only which forms were filled.

The filtering matters more than the upload. Google silently discards
conversions whose originating ad click is too old, so a bridge that uploads
everything looks like it worked and changes nothing:

    click identifier (gclid)   90 days
    hashed email               63 days

Deals older than the window are reported as skipped, never sent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .pipedrive import Deal, PipedriveError, hash_email

GCLID_MAX_AGE_DAYS = 90
EMAIL_MAX_AGE_DAYS = 63


@dataclass
class Prepared:
    """One deal, resolved into either an upload payload or a reason to skip."""

    deal_id: int
    title: str
    route: str | None
    conversion: dict | None
    skip_reason: str | None
    age_days: int | None


@dataclass
class BridgeResult:
    ready: list[dict] = field(default_factory=list)
    prepared: list[Prepared] = field(default_factory=list)

    def skipped(self) -> list[Prepared]:
        return [p for p in self.prepared if p.skip_reason]

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {"ready": len(self.ready)}
        for p in self.prepared:
            key = p.skip_reason.split(":")[0] if p.skip_reason else f"ready via {p.route}"
            counts[key] = counts.get(key, 0) + 1
        return counts


def _parse(when: str | None) -> datetime | None:
    if not when:
        return None
    text = str(when).strip().replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.fromisoformat(text) if fmt is None else datetime.strptime(text, fmt)
        except ValueError:
            continue
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def format_conversion_time(dt: datetime, offset: str = "+08:00") -> str:
    """Google wants 'YYYY-MM-DD HH:MM:SS+HH:MM' in the account's timezone."""
    sign = 1 if offset.startswith("+") else -1
    hours, _, minutes = offset[1:].partition(":")
    shifted = dt.astimezone(timezone.utc) + sign * timedelta(
        hours=int(hours), minutes=int(minutes or 0)
    )
    return shifted.strftime("%Y-%m-%d %H:%M:%S") + offset


def prepare(
    deals: list[Deal],
    *,
    value_map: dict[str, float] | None = None,
    default_value: float | None = None,
    currency: str = "HKD",
    tz_offset: str = "+08:00",
    now: datetime | None = None,
    prefer_gclid: bool = True,
) -> BridgeResult:
    """Turn Pipedrive deals into upload payloads, filtering what Google rejects.

    ``value_map`` maps deal status to a conversion value, so an unqualified or
    lost deal can be uploaded at zero rather than withheld. Sending the losers
    is what teaches Smart Bidding which sources to stop buying; sending only
    the winners leaves it optimising toward whoever fills forms most cheaply.
    """
    now = now or datetime.now(timezone.utc)
    result = BridgeResult()
    seen: set[int] = set()

    for deal in deals:
        if deal.id in seen:
            result.prepared.append(
                Prepared(deal.id, deal.title, None, None, "duplicate: already in this batch", None)
            )
            continue
        seen.add(deal.id)

        when = _parse(deal.conversion_time())
        if when is None:
            result.prepared.append(
                Prepared(deal.id, deal.title, None, None, "no usable date on the deal", None)
            )
            continue
        age = (now - when).days

        route = None
        if prefer_gclid and deal.gclid and age <= GCLID_MAX_AGE_DAYS:
            route = "gclid"
        elif deal.email and age <= EMAIL_MAX_AGE_DAYS:
            route = "email"

        if route is None:
            if not deal.gclid and not deal.email:
                reason = "no click id and no email on the deal"
            elif deal.gclid and age > GCLID_MAX_AGE_DAYS:
                reason = f"too old: {age} days, Google accepts {GCLID_MAX_AGE_DAYS} for a click id"
            else:
                reason = f"too old: {age} days, Google accepts {EMAIL_MAX_AGE_DAYS} for an email match"
            result.prepared.append(Prepared(deal.id, deal.title, None, None, reason, age))
            continue

        value = None
        if value_map and deal.status in value_map:
            value = float(value_map[deal.status])
        elif default_value is not None:
            value = float(default_value)
        elif deal.value is not None:
            value = float(deal.value)

        payload: dict = {
            "conversion_date_time": format_conversion_time(when, tz_offset),
            "order_id": f"pd-{deal.id}",
        }
        if route == "gclid":
            payload["gclid"] = deal.gclid
        else:
            try:
                payload["hashed_email"] = hash_email(deal.email or "")
            except PipedriveError as exc:
                result.prepared.append(
                    Prepared(deal.id, deal.title, None, None, f"bad email: {exc}", age)
                )
                continue
        if value is not None:
            payload["conversion_value"] = value
            payload["currency_code"] = deal.currency or currency

        result.ready.append(payload)
        result.prepared.append(Prepared(deal.id, deal.title, route, payload, None, age))

    return result
