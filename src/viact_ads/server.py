"""MCP server exposing the viAct Google Ads account to Claude.

Transport is stdio, so nothing may be written to stdout except MCP frames.
All diagnostics go to stderr.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

try:
    # MCP Python SDK >= 2.0
    from mcp.server import MCPServer as _Server
except ImportError:  # pragma: no cover - SDK 1.x fallback
    from mcp.server.fastmcp import FastMCP as _Server

from . import __version__, reports
from .client import GoogleAdsClient
from .config import ConfigError, load_config, normalize_customer_id

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("viact-ads")

mcp = _Server("viact-google-ads", version=__version__)

_client: GoogleAdsClient | None = None


def _get_client() -> GoogleAdsClient:
    """Build the client on first use so a missing .env surfaces as a readable
    tool error instead of a silent start-up crash."""
    global _client
    if _client is None:
        _client = GoogleAdsClient(load_config())
    return _client


def _result(query: str, rows: list[dict[str, Any]], customer_id: str | None) -> dict:
    return {
        "customer_id": customer_id,
        "row_count": len(rows),
        "rows": rows,
        "query": query.strip(),
    }


async def _run(query: str, customer_id: str | None) -> dict:
    client = _get_client()
    target = client._config.resolve_customer_id(customer_id)
    rows = await client.search(query, customer_id=target)
    return _result(query, rows, target)


# --------------------------------------------------------------------------
# Connection / discovery
# --------------------------------------------------------------------------


@mcp.tool()
async def check_connection() -> dict:
    """Verify the Google Ads credentials end to end.

    Confirms the refresh token still mints an access token and that the
    developer token is accepted. Run this first after setup — it reports
    exactly which step is broken.
    """
    try:
        config = load_config()
    except ConfigError as exc:
        return {"ok": False, "stage": "credentials", "error": str(exc)}

    client = _get_client()
    try:
        customers = await client.list_accessible_customers()
    except Exception as exc:  # surfaced to the user verbatim
        return {"ok": False, "stage": "google_ads_api", "error": str(exc)}

    return {
        "ok": True,
        "api_version": config.api_version,
        "login_customer_id": config.login_customer_id,
        "default_customer_id": config.default_customer_id,
        "accessible_customers": customers,
        "note": (
            "These are the accounts the authorised user can reach directly. "
            "Call list_managed_accounts to expand an MCC into its child accounts."
        ),
    }


@mcp.tool()
async def list_accessible_customers() -> dict:
    """List the Google Ads account IDs these credentials can reach directly.

    For an MCC login this is usually just the manager account itself.
    """
    customers = await _get_client().list_accessible_customers()
    return {"count": len(customers), "customer_ids": customers}


@mcp.tool()
async def list_managed_accounts(manager_customer_id: str | None = None) -> dict:
    """List every client account sitting under an MCC (manager) account.

    Args:
        manager_customer_id: The MCC to expand. Defaults to
            GOOGLE_ADS_LOGIN_CUSTOMER_ID.
    """
    client = _get_client()
    manager = (
        normalize_customer_id(manager_customer_id) or client._config.login_customer_id
    )
    if not manager:
        raise ConfigError(
            "No manager account given and GOOGLE_ADS_LOGIN_CUSTOMER_ID is unset. "
            "Pass manager_customer_id explicitly."
        )
    query = reports.managed_accounts()
    rows = await client.search(query, customer_id=manager, login_customer_id=manager)
    return _result(query, rows, manager)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


@mcp.tool()
async def account_summary(
    date_range: str = "LAST_30_DAYS",
    customer_id: str | None = None,
    segment_by_date: bool = False,
) -> dict:
    """Account-level totals: spend, clicks, impressions, conversions, CTR, CPC.

    Args:
        date_range: A preset such as LAST_7_DAYS, LAST_30_DAYS, THIS_MONTH,
            LAST_MONTH, or an explicit 'YYYY-MM-DD,YYYY-MM-DD' range.
        customer_id: Account to query. Defaults to GOOGLE_ADS_CUSTOMER_ID.
        segment_by_date: Return one row per day instead of a single total.
    """
    return await _run(reports.account_summary(date_range, segment_by_date), customer_id)


@mcp.tool()
async def campaign_performance(
    date_range: str = "LAST_30_DAYS",
    customer_id: str | None = None,
    status_filter: str = "ENABLED",
    segment_by_date: bool = False,
    limit: int = 200,
) -> dict:
    """Per-campaign performance, sorted by spend.

    Args:
        date_range: Preset or 'YYYY-MM-DD,YYYY-MM-DD'.
        customer_id: Account to query. Defaults to GOOGLE_ADS_CUSTOMER_ID.
        status_filter: ENABLED, PAUSED, REMOVED, or ALL.
        segment_by_date: Break each campaign out by day.
        limit: Maximum rows to return.
    """
    query = reports.campaign_performance(
        date_range, status_filter, segment_by_date, limit
    )
    return await _run(query, customer_id)


@mcp.tool()
async def ad_group_performance(
    date_range: str = "LAST_30_DAYS",
    customer_id: str | None = None,
    campaign_name_contains: str | None = None,
    limit: int = 200,
) -> dict:
    """Per-ad-group performance, sorted by spend.

    Args:
        date_range: Preset or 'YYYY-MM-DD,YYYY-MM-DD'.
        customer_id: Account to query. Defaults to GOOGLE_ADS_CUSTOMER_ID.
        campaign_name_contains: Restrict to campaigns whose name contains this text.
        limit: Maximum rows to return.
    """
    query = reports.ad_group_performance(date_range, campaign_name_contains, limit)
    return await _run(query, customer_id)


@mcp.tool()
async def keyword_performance(
    date_range: str = "LAST_30_DAYS",
    customer_id: str | None = None,
    campaign_name_contains: str | None = None,
    limit: int = 300,
) -> dict:
    """Keyword-level performance including match type and Quality Score.

    Args:
        date_range: Preset or 'YYYY-MM-DD,YYYY-MM-DD'.
        customer_id: Account to query. Defaults to GOOGLE_ADS_CUSTOMER_ID.
        campaign_name_contains: Restrict to campaigns whose name contains this text.
        limit: Maximum rows to return.
    """
    query = reports.keyword_performance(date_range, campaign_name_contains, limit)
    return await _run(query, customer_id)


@mcp.tool()
async def search_terms_report(
    date_range: str = "LAST_30_DAYS",
    customer_id: str | None = None,
    campaign_name_contains: str | None = None,
    min_impressions: int = 1,
    limit: int = 500,
) -> dict:
    """The actual queries people typed before seeing an ad.

    This is the raw material for negative-keyword and wasted-spend analysis.

    Args:
        date_range: Preset or 'YYYY-MM-DD,YYYY-MM-DD'.
        customer_id: Account to query. Defaults to GOOGLE_ADS_CUSTOMER_ID.
        campaign_name_contains: Restrict to campaigns whose name contains this text.
        min_impressions: Drop terms below this impression count.
        limit: Maximum rows to return.
    """
    query = reports.search_terms(
        date_range, campaign_name_contains, min_impressions, limit
    )
    return await _run(query, customer_id)


@mcp.tool()
async def ad_performance(
    date_range: str = "LAST_30_DAYS",
    customer_id: str | None = None,
    limit: int = 200,
) -> dict:
    """Per-ad performance including ad strength and final URLs.

    Args:
        date_range: Preset or 'YYYY-MM-DD,YYYY-MM-DD'.
        customer_id: Account to query. Defaults to GOOGLE_ADS_CUSTOMER_ID.
        limit: Maximum rows to return.
    """
    return await _run(reports.ad_performance(date_range, limit), customer_id)


@mcp.tool()
async def run_gaql(query: str, customer_id: str | None = None) -> dict:
    """Run an arbitrary GAQL query — the escape hatch for anything not covered above.

    Field names are snake_case (e.g. metrics.cost_micros). Always include a
    LIMIT. Money is returned in micros, with a divided-by-1,000,000 companion
    field added alongside each one.

    Example:
        SELECT campaign.name, metrics.cost_micros
        FROM campaign
        WHERE segments.date DURING LAST_7_DAYS
        ORDER BY metrics.cost_micros DESC
        LIMIT 50

    Args:
        query: The GAQL query text.
        customer_id: Account to query. Defaults to GOOGLE_ADS_CUSTOMER_ID.
    """
    if not query or not query.strip():
        raise ValueError("query is required.")
    return await _run(query, customer_id)


def main() -> None:
    log.info("Starting viAct Google Ads MCP server (stdio)")
    mcp.run()


if __name__ == "__main__":
    main()
