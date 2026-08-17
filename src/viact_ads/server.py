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

from . import __version__, mutations, reports
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


# --------------------------------------------------------------------------
# Writes
#
# Every write tool takes `confirm`. Left false (the default) the operations are
# sent to Google with validateOnly set: they are checked against the real
# account and nothing changes. The same payload is what later gets applied, so
# a clean preview means the apply will behave identically.
# --------------------------------------------------------------------------


async def _apply(
    service: str,
    operations: list[dict],
    customer_id: str,
    confirm: bool,
    before: list[dict] | None = None,
) -> dict:
    client = _get_client()
    result = await client.mutate(
        service, operations, customer_id=customer_id, validate_only=not confirm
    )

    if not confirm:
        return {
            "applied": False,
            "customer_id": customer_id,
            "operation_count": len(operations),
            "current_state": before or "not looked up for this entity type",
            "operations": operations,
            "validated_by_google": "OK — this request is valid and would succeed",
            "next_step": (
                "Nothing has changed. Show the user what would change and get "
                "their approval, then call this tool again with confirm=true."
            ),
        }

    changed = result.get("results", [])
    return {
        "applied": True,
        "customer_id": customer_id,
        "changed_count": len(changed),
        "resource_names": [r.get("resourceName") for r in changed],
    }


async def _lookup(query: str, customer_id: str) -> list[dict]:
    """Best-effort current-state read so a preview can show a real before/after."""
    try:
        return await _get_client().search(query, customer_id=customer_id)
    except Exception as exc:  # a failed preview lookup must not block the preview
        log.warning("State lookup failed: %s", exc)
        return []


@mcp.tool()
async def set_status(
    entity_type: str,
    entity_ids: list[str],
    status: str,
    customer_id: str | None = None,
    confirm: bool = False,
) -> dict:
    """Pause, enable, or remove campaigns, ad groups, keywords, or ads.

    Args:
        entity_type: campaign, ad_group, keyword, or ad.
        entity_ids: IDs to change. Keywords and ads need the composite form
            'adGroupId~criterionId' / 'adGroupId~adId'.
        status: ENABLED, PAUSED, or REMOVED. REMOVED cannot be undone.
        customer_id: Account to act on. Defaults to GOOGLE_ADS_CUSTOMER_ID.
        confirm: Leave false to preview. Set true only after the user approves.
    """
    target = _get_client()._config.resolve_customer_id(customer_id)
    service, operations = mutations.set_status(
        entity_type, target, entity_ids, status
    )

    before: list[dict] = []
    ids = ", ".join(str(i) for i in entity_ids)
    if entity_type == "campaign":
        before = await _lookup(
            "SELECT campaign.id, campaign.name, campaign.status, "
            "campaign_budget.amount_micros FROM campaign "
            f"WHERE campaign.id IN ({ids})",
            target,
        )
    elif entity_type == "ad_group":
        before = await _lookup(
            "SELECT ad_group.id, ad_group.name, ad_group.status, campaign.name "
            f"FROM ad_group WHERE ad_group.id IN ({ids})",
            target,
        )

    return await _apply(service, operations, target, confirm, before)


@mcp.tool()
async def add_negative_keywords(
    keywords: list[str],
    match_type: str = "PHRASE",
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    customer_id: str | None = None,
    confirm: bool = False,
) -> dict:
    """Block search queries at campaign or ad group level.

    Args:
        keywords: Terms to block.
        match_type: EXACT, PHRASE, or BROAD. PHRASE is the usual choice.
        campaign_id: Block across the whole campaign. Give this or ad_group_id.
        ad_group_id: Block within one ad group only.
        customer_id: Account to act on. Defaults to GOOGLE_ADS_CUSTOMER_ID.
        confirm: Leave false to preview. Set true only after the user approves.
    """
    target = _get_client()._config.resolve_customer_id(customer_id)
    service, operations = mutations.add_negative_keywords(
        target, keywords, match_type, campaign_id, ad_group_id
    )
    return await _apply(service, operations, target, confirm)


@mcp.tool()
async def list_negative_keywords(
    campaign_id: str | None = None,
    customer_id: str | None = None,
    limit: int = 500,
) -> dict:
    """List existing negative keywords and their resource names.

    Read-only. The resource names it returns are what remove_negative_keywords
    needs.
    """
    where = "campaign_criterion.negative = TRUE"
    if campaign_id:
        where += f" AND campaign.id = {int(campaign_id)}"
    query = (
        "SELECT campaign.id, campaign.name, campaign_criterion.resource_name,\n"
        "       campaign_criterion.keyword.text,\n"
        "       campaign_criterion.keyword.match_type\n"
        f"FROM campaign_criterion\nWHERE {where}\nLIMIT {int(limit)}"
    )
    return await _run(query, customer_id)


@mcp.tool()
async def remove_negative_keywords(
    resource_names: list[str],
    customer_id: str | None = None,
    confirm: bool = False,
) -> dict:
    """Remove campaign-level negative keywords by resource name.

    Args:
        resource_names: Full resource names from list_negative_keywords.
        customer_id: Account to act on. Defaults to GOOGLE_ADS_CUSTOMER_ID.
        confirm: Leave false to preview. Set true only after the user approves.
    """
    target = _get_client()._config.resolve_customer_id(customer_id)
    service, operations = mutations.remove_criteria(
        resource_names, "campaign_criterion"
    )
    return await _apply(service, operations, target, confirm)


@mcp.tool()
async def list_shared_negative_lists(customer_id: str | None = None) -> dict:
    """List the shared exclusion lists under Shared Library.

    Read-only. Names are not unique — an archived list often shares a name with
    the live one — so check `shared_set.status` before acting on an ID.
    """
    query = (
        "SELECT shared_set.id, shared_set.name, shared_set.type,\n"
        "       shared_set.status, shared_set.member_count\n"
        "FROM shared_set\nWHERE shared_set.type = 'NEGATIVE_KEYWORDS'\n"
        "ORDER BY shared_set.name"
    )
    return await _run(query, customer_id)


@mcp.tool()
async def list_shared_negative_keywords(
    shared_set_id: str,
    customer_id: str | None = None,
    limit: int = 5000,
) -> dict:
    """List the terms inside a shared exclusion list.

    Read-only. Match type matters: an EXACT negative blocks only that precise
    query, while PHRASE and BROAD reach much further.
    """
    query = (
        "SELECT shared_set.id, shared_set.name, shared_criterion.criterion_id,\n"
        "       shared_criterion.keyword.text, shared_criterion.keyword.match_type\n"
        f"FROM shared_criterion\nWHERE shared_set.id = {int(shared_set_id)}\n"
        f"LIMIT {int(limit)}"
    )
    return await _run(query, customer_id)


@mcp.tool()
async def which_campaigns_use_shared_list(
    shared_set_id: str, customer_id: str | None = None
) -> dict:
    """Show which campaigns a shared exclusion list is attached to.

    Read-only. A list attached to nothing has no effect, however alarming its
    contents; one on your top campaigns affects most of your spend.
    """
    query = (
        "SELECT campaign.id, campaign.name, campaign.status, shared_set.name\n"
        f"FROM campaign_shared_set\nWHERE shared_set.id = {int(shared_set_id)}\n"
        "LIMIT 500"
    )
    return await _run(query, customer_id)


@mcp.tool()
async def remove_shared_negative_keywords(
    shared_set_id: str,
    keywords: list[str],
    customer_id: str | None = None,
    confirm: bool = False,
) -> dict:
    """Remove terms from a shared exclusion list, unblocking that traffic.

    Args:
        shared_set_id: The list to edit, from list_shared_negative_lists.
        keywords: Exact keyword texts to remove. Matched case-insensitively
            against the list; anything not found is reported rather than
            silently skipped.
        customer_id: Account to act on. Defaults to GOOGLE_ADS_CUSTOMER_ID.
        confirm: Leave false to preview. Set true only after the user approves.

    Terms are resolved by text rather than taken as IDs, so a mistyped ID
    cannot remove some unrelated term. Removing a negative lets queries through
    again, which can start costing money immediately — the preview lists every
    campaign the list feeds.
    """
    target = _get_client()._config.resolve_customer_id(customer_id)
    wanted = [k.strip() for k in keywords if k and k.strip()]
    if not wanted:
        raise mutations.MutationError("keywords must not be empty.")

    existing = await _lookup(
        "SELECT shared_criterion.criterion_id, shared_criterion.keyword.text,\n"
        "       shared_criterion.keyword.match_type\n"
        f"FROM shared_criterion WHERE shared_set.id = {int(shared_set_id)} LIMIT 10000",
        target,
    )
    by_text: dict[str, list[dict]] = {}
    for row in existing:
        text = str(row.get("shared_criterion.keyword.text", "")).strip().lower()
        by_text.setdefault(text, []).append(row)

    matched, not_found = [], []
    for term in wanted:
        hits = by_text.get(term.lower())
        if not hits:
            not_found.append(term)
            continue
        for hit in hits:
            matched.append(
                {
                    "criterion_id": hit.get("shared_criterion.criterion_id"),
                    "text": hit.get("shared_criterion.keyword.text"),
                    "match_type": hit.get("shared_criterion.keyword.match_type"),
                }
            )

    if not matched:
        raise mutations.MutationError(
            f"None of these terms are in shared set {shared_set_id}: "
            + ", ".join(wanted)
        )

    service, operations = mutations.remove_shared_criteria(
        target, shared_set_id, [m["criterion_id"] for m in matched]
    )
    result = await _apply(service, operations, target, confirm)
    result["shared_set_id"] = shared_set_id
    result["matched"] = matched
    result["not_found"] = not_found
    if not confirm:
        result["affected_campaigns"] = await _lookup(
            "SELECT campaign.name, campaign.status FROM campaign_shared_set "
            f"WHERE shared_set.id = {int(shared_set_id)} LIMIT 500",
            target,
        )
    return result


@mcp.tool()
async def update_campaign_budget(
    daily_amount: float,
    campaign_id: str | None = None,
    budget_id: str | None = None,
    customer_id: str | None = None,
    confirm: bool = False,
) -> dict:
    """Change a campaign's daily budget.

    Args:
        daily_amount: New daily budget in account currency (e.g. 175.0), not micros.
        campaign_id: The campaign whose budget to change; its budget is looked up.
        budget_id: Alternatively, target a budget directly.
        customer_id: Account to act on. Defaults to GOOGLE_ADS_CUSTOMER_ID.
        confirm: Leave false to preview. Set true only after the user approves.

    A shared budget affects every campaign attached to it — the preview lists
    them so that is visible before applying.
    """
    target = _get_client()._config.resolve_customer_id(customer_id)

    if not campaign_id and not budget_id:
        raise mutations.MutationError("Give either campaign_id or budget_id.")

    before: list[dict] = []
    if campaign_id:
        before = await _lookup(
            "SELECT campaign.id, campaign.name, campaign_budget.id, "
            "campaign_budget.name, campaign_budget.amount_micros, "
            "campaign_budget.explicitly_shared FROM campaign "
            f"WHERE campaign.id = {int(campaign_id)}",
            target,
        )
        if not before:
            raise mutations.MutationError(
                f"Campaign {campaign_id} not found in account {target}."
            )
        budget_id = str(before[0].get("campaign_budget.id"))
    else:
        before = await _lookup(
            "SELECT campaign.name, campaign_budget.id, campaign_budget.name, "
            "campaign_budget.amount_micros, campaign_budget.explicitly_shared "
            f"FROM campaign WHERE campaign_budget.id = {int(budget_id)}",
            target,
        )

    service, operations = mutations.update_budget(target, budget_id, daily_amount)
    result = await _apply(service, operations, target, confirm, before)
    if not confirm:
        result["new_daily_amount"] = daily_amount
        result["campaigns_sharing_this_budget"] = len(before)
    return result


@mcp.tool()
async def create_campaign_budget(
    name: str,
    daily_amount: float,
    shared: bool = False,
    customer_id: str | None = None,
    confirm: bool = False,
) -> dict:
    """Create a budget, which a new campaign needs before it can exist.

    Args:
        name: Budget name, unique within the account.
        daily_amount: Daily budget in account currency, not micros.
        shared: Whether several campaigns may draw on it.
        customer_id: Account to act on. Defaults to GOOGLE_ADS_CUSTOMER_ID.
        confirm: Leave false to preview. Set true only after the user approves.
    """
    target = _get_client()._config.resolve_customer_id(customer_id)
    service, operations = mutations.create_budget(target, name, daily_amount, shared)
    return await _apply(service, operations, target, confirm)


@mcp.tool()
async def update_bid(
    entity_type: str,
    entity_id: str,
    bid: float,
    customer_id: str | None = None,
    confirm: bool = False,
) -> dict:
    """Set a max CPC bid on an ad group or a keyword.

    Args:
        entity_type: ad_group or keyword.
        entity_id: Ad group ID, or 'adGroupId~criterionId' for a keyword.
        bid: Max CPC in account currency (e.g. 8.50), not micros.
        customer_id: Account to act on. Defaults to GOOGLE_ADS_CUSTOMER_ID.
        confirm: Leave false to preview. Set true only after the user approves.

    Only meaningful on manual bidding. Automated strategies ignore these.
    """
    target = _get_client()._config.resolve_customer_id(customer_id)
    service, operations = mutations.update_bid(entity_type, target, entity_id, bid)
    return await _apply(service, operations, target, confirm)


@mcp.tool()
async def update_bidding_strategy(
    campaign_id: str,
    strategy: str,
    target_value: float | None = None,
    customer_id: str | None = None,
    confirm: bool = False,
) -> dict:
    """Switch a campaign's bidding strategy.

    Args:
        campaign_id: Campaign to change.
        strategy: MANUAL_CPC, MAXIMIZE_CONVERSIONS, MAXIMIZE_CONVERSION_VALUE,
            TARGET_CPA, TARGET_ROAS, or TARGET_SPEND.
        target_value: Cost per acquisition for TARGET_CPA; a ratio for
            TARGET_ROAS (2.5 means 250%). Ignored by the others.
        customer_id: Account to act on. Defaults to GOOGLE_ADS_CUSTOMER_ID.
        confirm: Leave false to preview. Set true only after the user approves.

    Changing strategy resets the learning period and usually disturbs
    performance for a week or two.
    """
    target = _get_client()._config.resolve_customer_id(customer_id)
    before = await _lookup(
        "SELECT campaign.id, campaign.name, campaign.bidding_strategy_type "
        f"FROM campaign WHERE campaign.id = {int(campaign_id)}",
        target,
    )
    service, operations = mutations.update_bidding_strategy(
        target, campaign_id, strategy, target_value
    )
    return await _apply(service, operations, target, confirm, before)


@mcp.tool()
async def create_campaign(
    name: str,
    budget_id: str,
    channel_type: str = "SEARCH",
    status: str = "PAUSED",
    strategy: str = "MANUAL_CPC",
    start_date: str | None = None,
    end_date: str | None = None,
    customer_id: str | None = None,
    confirm: bool = False,
) -> dict:
    """Create a campaign. Defaults to PAUSED so it cannot start spending unattended.

    Args:
        name: Campaign name.
        budget_id: An existing budget's ID — make one with create_campaign_budget.
        channel_type: SEARCH, DISPLAY, SHOPPING, VIDEO, PERFORMANCE_MAX, DEMAND_GEN.
        status: ENABLED or PAUSED. PAUSED is strongly preferred for a new campaign.
        strategy: Bidding strategy, as in update_bidding_strategy.
        start_date: YYYY-MM-DD. Defaults to today if omitted.
        end_date: YYYY-MM-DD. Defaults to no end date.
        customer_id: Account to act on. Defaults to GOOGLE_ADS_CUSTOMER_ID.
        confirm: Leave false to preview. Set true only after the user approves.

    A campaign alone serves nothing — it still needs an ad group, ads, and
    keywords or targeting.
    """
    target = _get_client()._config.resolve_customer_id(customer_id)
    budget_resource = mutations.resource_name("campaign_budget", target, budget_id)
    service, operations = mutations.create_campaign(
        target, name, budget_resource, channel_type, status, strategy,
        start_date, end_date,
    )
    return await _apply(service, operations, target, confirm)


@mcp.tool()
async def create_ad_group(
    campaign_id: str,
    name: str,
    cpc_bid: float | None = None,
    status: str = "PAUSED",
    customer_id: str | None = None,
    confirm: bool = False,
) -> dict:
    """Create an ad group inside a campaign.

    Args:
        campaign_id: Parent campaign.
        name: Ad group name.
        cpc_bid: Default max CPC in account currency, not micros.
        status: ENABLED or PAUSED.
        customer_id: Account to act on. Defaults to GOOGLE_ADS_CUSTOMER_ID.
        confirm: Leave false to preview. Set true only after the user approves.
    """
    target = _get_client()._config.resolve_customer_id(customer_id)
    service, operations = mutations.create_ad_group(
        target, campaign_id, name, cpc_bid, status
    )
    return await _apply(service, operations, target, confirm)


@mcp.tool()
async def create_responsive_search_ad(
    ad_group_id: str,
    headlines: list[str],
    descriptions: list[str],
    final_url: str,
    path1: str | None = None,
    path2: str | None = None,
    status: str = "PAUSED",
    customer_id: str | None = None,
    confirm: bool = False,
) -> dict:
    """Create a responsive search ad.

    Args:
        ad_group_id: Ad group to hold the ad.
        headlines: 3-15 headlines, each 30 characters or fewer.
        descriptions: 2-4 descriptions, each 90 characters or fewer.
        final_url: Landing page URL, including https://.
        path1: Optional display path segment, 15 characters or fewer.
        path2: Optional second display path segment.
        status: ENABLED or PAUSED.
        customer_id: Account to act on. Defaults to GOOGLE_ADS_CUSTOMER_ID.
        confirm: Leave false to preview. Set true only after the user approves.

    Lengths are checked before anything is sent, so an over-long headline is
    reported rather than rejected by Google.
    """
    target = _get_client()._config.resolve_customer_id(customer_id)
    service, operations = mutations.create_responsive_search_ad(
        target, ad_group_id, headlines, descriptions, final_url, path1, path2, status
    )
    return await _apply(service, operations, target, confirm)


@mcp.tool()
async def add_keywords(
    ad_group_id: str,
    keywords: list[str],
    match_type: str = "PHRASE",
    bid: float | None = None,
    customer_id: str | None = None,
    confirm: bool = False,
) -> dict:
    """Add positive keywords to an ad group.

    Args:
        ad_group_id: Ad group to add them to.
        keywords: Keyword texts.
        match_type: EXACT, PHRASE, or BROAD.
        bid: Optional max CPC per keyword, in account currency.
        customer_id: Account to act on. Defaults to GOOGLE_ADS_CUSTOMER_ID.
        confirm: Leave false to preview. Set true only after the user approves.
    """
    target = _get_client()._config.resolve_customer_id(customer_id)
    service, operations = mutations.add_keywords(
        target, ad_group_id, keywords, match_type, bid
    )
    return await _apply(service, operations, target, confirm)


@mcp.tool()
async def upload_offline_conversions(
    conversion_action_id: str,
    conversions: list[dict],
    customer_id: str | None = None,
    confirm: bool = False,
) -> dict:
    """Upload offline conversions against recorded ad clicks.

    Args:
        conversion_action_id: The conversion action to attribute to. Find IDs with
            run_gaql: SELECT conversion_action.id, conversion_action.name
            FROM conversion_action.
        conversions: One dict per conversion, each with exactly one click
            identifier (gclid, gbraid, or wbraid), a conversion_date_time as
            'YYYY-MM-DD HH:MM:SS+HH:MM' in the account timezone, and optionally
            conversion_value, currency_code, and order_id.
        customer_id: Account to act on. Defaults to GOOGLE_ADS_CUSTOMER_ID.
        confirm: Leave false to preview. Set true only after the user approves.

    Google accepts clicks up to 90 days old. Uploaded conversions feed Smart
    Bidding, so a bad upload distorts bidding for weeks.
    """
    target = _get_client()._config.resolve_customer_id(customer_id)
    payload = mutations.build_click_conversions(
        target, conversion_action_id, conversions
    )
    client = _get_client()
    result = await client.upload_click_conversions(
        payload, customer_id=target, validate_only=not confirm
    )

    if not confirm:
        return {
            "applied": False,
            "customer_id": target,
            "conversion_count": len(payload),
            "conversions": payload,
            "validated_by_google": "OK — this upload is valid and would succeed",
            "next_step": (
                "Nothing has been uploaded. Get the user's approval, then call "
                "again with confirm=true."
            ),
        }
    return {
        "applied": True,
        "customer_id": target,
        "uploaded_count": len(result.get("results", [])),
    }


def main() -> None:
    log.info("Starting viAct Google Ads MCP server (stdio)")
    mcp.run()


if __name__ == "__main__":
    main()
