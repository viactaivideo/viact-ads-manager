"""GAQL builders for the reports we expose as MCP tools."""

from __future__ import annotations

import re

# Date literals GAQL understands natively.
DATE_PRESETS = {
    "TODAY",
    "YESTERDAY",
    "LAST_7_DAYS",
    "LAST_14_DAYS",
    "LAST_30_DAYS",
    "LAST_BUSINESS_WEEK",
    "LAST_WEEK_MON_SUN",
    "LAST_WEEK_SUN_SAT",
    "THIS_WEEK_MON_TODAY",
    "THIS_WEEK_SUN_TODAY",
    "THIS_MONTH",
    "LAST_MONTH",
    "ALL_TIME",
}

_EXPLICIT_RANGE = re.compile(
    r"^\s*(\d{4}-\d{2}-\d{2})\s*(?:,|\.\.|to)\s*(\d{4}-\d{2}-\d{2})\s*$",
    re.IGNORECASE,
)

CORE_METRICS = (
    "metrics.impressions",
    "metrics.clicks",
    "metrics.ctr",
    "metrics.average_cpc",
    "metrics.cost_micros",
    "metrics.conversions",
    "metrics.conversions_value",
    "metrics.cost_per_conversion",
)


class ReportError(ValueError):
    """Raised when report arguments cannot be turned into valid GAQL."""


def date_clause(date_range: str) -> str:
    """Turn a preset or an explicit range into a GAQL WHERE fragment."""
    value = (date_range or "").strip()
    if not value:
        raise ReportError("date_range is required.")

    upper = value.upper().replace(" ", "_")
    if upper in DATE_PRESETS:
        if upper == "ALL_TIME":
            return ""
        return f"segments.date DURING {upper}"

    match = _EXPLICIT_RANGE.match(value)
    if match:
        start, end = match.group(1), match.group(2)
        if start > end:
            raise ReportError(
                f"date_range start {start} is after end {end}."
            )
        return f"segments.date BETWEEN '{start}' AND '{end}'"

    raise ReportError(
        f"Unrecognised date_range {date_range!r}. Use a preset "
        f"({', '.join(sorted(DATE_PRESETS))}) or an explicit "
        f"'YYYY-MM-DD,YYYY-MM-DD' range."
    )


def _build(
    select: tuple[str, ...],
    resource: str,
    date_range: str,
    *,
    extra_where: tuple[str, ...] = (),
    segment_by_date: bool = False,
    order_by: str = "metrics.cost_micros DESC",
    limit: int = 200,
) -> str:
    fields = list(select)
    if segment_by_date:
        fields.insert(0, "segments.date")

    conditions = [c for c in (date_clause(date_range), *extra_where) if c]

    query = f"SELECT {', '.join(fields)}\nFROM {resource}"
    if conditions:
        query += "\nWHERE " + "\n  AND ".join(conditions)
    if order_by:
        query += f"\nORDER BY {order_by}"
    query += f"\nLIMIT {int(limit)}"
    return query


def managed_accounts() -> str:
    """Every account under the MCC this query is run against."""
    return (
        "SELECT customer_client.id, customer_client.descriptive_name,\n"
        "       customer_client.currency_code, customer_client.time_zone,\n"
        "       customer_client.manager, customer_client.level,\n"
        "       customer_client.status\n"
        "FROM customer_client\n"
        "WHERE customer_client.status = 'ENABLED'\n"
        "ORDER BY customer_client.level, customer_client.id"
    )


def account_summary(date_range: str, segment_by_date: bool = False) -> str:
    return _build(
        (
            "customer.id",
            "customer.descriptive_name",
            "customer.currency_code",
            *CORE_METRICS,
        ),
        "customer",
        date_range,
        segment_by_date=segment_by_date,
        order_by="segments.date" if segment_by_date else "",
        limit=1000 if segment_by_date else 10,
    )


def campaign_performance(
    date_range: str,
    status_filter: str | None = "ENABLED",
    segment_by_date: bool = False,
    limit: int = 200,
) -> str:
    where: tuple[str, ...] = ()
    if status_filter and status_filter.upper() != "ALL":
        where = (f"campaign.status = '{_status(status_filter)}'",)
    return _build(
        (
            "campaign.id",
            "campaign.name",
            "campaign.status",
            "campaign.advertising_channel_type",
            "campaign_budget.amount_micros",
            *CORE_METRICS,
        ),
        "campaign",
        date_range,
        extra_where=where,
        segment_by_date=segment_by_date,
        limit=limit,
    )


def ad_group_performance(
    date_range: str,
    campaign_name_contains: str | None = None,
    limit: int = 200,
) -> str:
    where: tuple[str, ...] = ("ad_group.status != 'REMOVED'",)
    if campaign_name_contains:
        where += (f"campaign.name LIKE '%{_escape(campaign_name_contains)}%'",)
    return _build(
        (
            "campaign.name",
            "ad_group.id",
            "ad_group.name",
            "ad_group.status",
            *CORE_METRICS,
        ),
        "ad_group",
        date_range,
        extra_where=where,
        limit=limit,
    )


def keyword_performance(
    date_range: str,
    campaign_name_contains: str | None = None,
    limit: int = 300,
) -> str:
    where: tuple[str, ...] = ("ad_group_criterion.status != 'REMOVED'",)
    if campaign_name_contains:
        where += (f"campaign.name LIKE '%{_escape(campaign_name_contains)}%'",)
    return _build(
        (
            "campaign.name",
            "ad_group.name",
            "ad_group_criterion.criterion_id",
            "ad_group_criterion.keyword.text",
            "ad_group_criterion.keyword.match_type",
            "ad_group_criterion.status",
            "ad_group_criterion.quality_info.quality_score",
            *CORE_METRICS,
        ),
        "keyword_view",
        date_range,
        extra_where=where,
        limit=limit,
    )


def search_terms(
    date_range: str,
    campaign_name_contains: str | None = None,
    min_impressions: int = 1,
    limit: int = 500,
) -> str:
    where: tuple[str, ...] = (f"metrics.impressions >= {int(min_impressions)}",)
    if campaign_name_contains:
        where += (f"campaign.name LIKE '%{_escape(campaign_name_contains)}%'",)
    return _build(
        (
            "search_term_view.search_term",
            "search_term_view.status",
            "campaign.name",
            "ad_group.name",
            "segments.search_term_match_type",
            *CORE_METRICS,
        ),
        "search_term_view",
        date_range,
        extra_where=where,
        limit=limit,
    )


def ad_performance(date_range: str, limit: int = 200) -> str:
    return _build(
        (
            "campaign.name",
            "ad_group.name",
            "ad_group_ad.ad.id",
            "ad_group_ad.ad.type",
            "ad_group_ad.status",
            "ad_group_ad.ad.final_urls",
            "ad_group_ad.ad_strength",
            *CORE_METRICS,
        ),
        "ad_group_ad",
        date_range,
        extra_where=("ad_group_ad.status != 'REMOVED'",),
        limit=limit,
    )


def _status(value: str) -> str:
    allowed = {"ENABLED", "PAUSED", "REMOVED"}
    upper = value.strip().upper()
    if upper not in allowed:
        raise ReportError(
            f"status_filter must be one of ENABLED, PAUSED, REMOVED, ALL — got {value!r}."
        )
    return upper


def _escape(value: str) -> str:
    """Neutralise quotes so a filter string cannot break out of its literal."""
    return value.replace("\\", "\\\\").replace("'", "\\'")
