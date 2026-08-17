"""Tests that do not touch the network.

The Google Ads API is stubbed with httpx.MockTransport, so these verify our
own logic: GAQL construction, response flattening, and error reporting.
"""

from __future__ import annotations

import json

import httpx
import pytest

from viact_ads import reports
from viact_ads.auth import AuthError
from viact_ads.client import GoogleAdsClient, GoogleAdsError, _add_currency_fields, _flatten
from viact_ads.config import Config, ConfigError, normalize_customer_id


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------


def test_normalize_customer_id_strips_formatting():
    assert normalize_customer_id("123-456-7890") == "1234567890"
    assert normalize_customer_id("1234567890") == "1234567890"
    assert normalize_customer_id(None) is None
    assert normalize_customer_id("") is None


def test_normalize_customer_id_rejects_wrong_length():
    with pytest.raises(ConfigError, match="10 digits"):
        normalize_customer_id("12345")


def test_resolve_customer_id_prefers_argument():
    config = _config(default_customer_id="1111111111")
    assert config.resolve_customer_id("222-222-2222") == "2222222222"
    assert config.resolve_customer_id(None) == "1111111111"


def test_resolve_customer_id_without_default_raises():
    with pytest.raises(ConfigError, match="No customer_id given"):
        _config(default_customer_id=None).resolve_customer_id(None)


# --------------------------------------------------------------------------
# GAQL construction
# --------------------------------------------------------------------------


def test_date_clause_presets_and_explicit_ranges():
    assert reports.date_clause("LAST_30_DAYS") == "segments.date DURING LAST_30_DAYS"
    assert reports.date_clause("last_7_days") == "segments.date DURING LAST_7_DAYS"
    assert reports.date_clause("ALL_TIME") == ""
    assert (
        reports.date_clause("2026-07-01,2026-07-31")
        == "segments.date BETWEEN '2026-07-01' AND '2026-07-31'"
    )


def test_date_clause_rejects_bad_input():
    with pytest.raises(reports.ReportError, match="Unrecognised date_range"):
        reports.date_clause("last month or so")
    with pytest.raises(reports.ReportError, match="is after end"):
        reports.date_clause("2026-08-31,2026-08-01")


def test_campaign_query_shape():
    query = reports.campaign_performance("LAST_7_DAYS", status_filter="ENABLED")
    assert "FROM campaign" in query
    assert "campaign.status = 'ENABLED'" in query
    assert "segments.date DURING LAST_7_DAYS" in query
    assert query.rstrip().endswith("LIMIT 200")
    # Without segment_by_date there must be no per-day breakdown.
    assert "segments.date," not in query


def test_campaign_query_all_statuses_has_no_status_filter():
    assert "campaign.status" not in reports.campaign_performance(
        "LAST_7_DAYS", status_filter="ALL"
    ).split("WHERE")[1]


def test_segment_by_date_adds_date_column():
    query = reports.campaign_performance("LAST_7_DAYS", segment_by_date=True)
    assert query.startswith("SELECT segments.date,")


def test_search_terms_query_applies_impression_floor():
    query = reports.search_terms("LAST_30_DAYS", min_impressions=25)
    assert "FROM search_term_view" in query
    assert "metrics.impressions >= 25" in query


def test_filter_values_are_escaped():
    """A quote in user input must not break out of the GAQL string literal."""
    query = reports.ad_group_performance("LAST_7_DAYS", campaign_name_contains="viAct's")
    assert r"campaign.name LIKE '%viAct\'s%'" in query


def test_invalid_status_filter_rejected():
    with pytest.raises(reports.ReportError, match="status_filter must be"):
        reports.campaign_performance("LAST_7_DAYS", status_filter="ACTIVE")


# --------------------------------------------------------------------------
# Response handling
# --------------------------------------------------------------------------


def test_flatten_converts_camel_case_to_dotted_snake_case():
    row = {
        "campaign": {"id": "123", "name": "Brand"},
        "metrics": {"costMicros": "45000000", "averageCpc": "1500000"},
    }
    assert _flatten(row) == {
        "campaign.id": "123",
        "campaign.name": "Brand",
        "metrics.cost_micros": "45000000",
        "metrics.average_cpc": "1500000",
    }


def test_currency_fields_are_added_alongside_micros():
    row = _add_currency_fields({"metrics.cost_micros": "45000000"})
    assert row["metrics.cost_micros"] == "45000000"
    assert row["metrics.cost"] == 45.0


def test_currency_conversion_ignores_non_numeric():
    row = _add_currency_fields({"metrics.cost_micros": None})
    assert "metrics.cost" not in row


def test_implicit_micros_fields_are_converted_in_place():
    """average_cpc and cost_per_conversion are micros despite the name."""
    row = _add_currency_fields(
        {
            "metrics.average_cpc": 6992649.575888569,
            "metrics.cost_per_conversion": 647053174.0888889,
        }
    )
    assert row["metrics.average_cpc"] == 6.9926
    assert row["metrics.cost_per_conversion"] == 647.0532


def test_non_money_metrics_are_left_alone():
    row = _add_currency_fields({"metrics.ctr": 0.0031, "metrics.clicks": "4164"})
    assert row == {"metrics.ctr": 0.0031, "metrics.clicks": "4164"}


# --------------------------------------------------------------------------
# Client behaviour against a stubbed API
# --------------------------------------------------------------------------


@pytest.mark.anyio
async def test_search_parses_stream_batches_and_sends_headers():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json=[
                {"results": [{"campaign": {"name": "A"}, "metrics": {"costMicros": "2000000"}}]},
                {"results": [{"campaign": {"name": "B"}, "metrics": {"costMicros": "1000000"}}]},
            ],
        )

    client = _client(handler)
    rows = await client.search("SELECT campaign.name FROM campaign", customer_id="2222222222")

    assert [r["campaign.name"] for r in rows] == ["A", "B"]
    assert rows[0]["metrics.cost"] == 2.0
    assert seen["url"].endswith("/v25/customers/2222222222/googleAds:searchStream")
    assert seen["headers"]["developer-token"] == "dev-token"
    assert seen["headers"]["login-customer-id"] == "1111111111"
    assert seen["headers"]["authorization"] == "Bearer tok"
    assert seen["body"] == {"query": "SELECT campaign.name FROM campaign"}
    await client.aclose()


@pytest.mark.anyio
async def test_access_token_is_cached_across_calls():
    calls = {"token": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            calls["token"] += 1
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(200, json=[{"results": []}])

    client = _client(handler)
    await client.search("SELECT campaign.id FROM campaign", customer_id="2222222222")
    await client.search("SELECT campaign.id FROM campaign", customer_id="2222222222")
    assert calls["token"] == 1
    await client.aclose()


@pytest.mark.anyio
async def test_unapproved_developer_token_gets_actionable_hint():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(
            403,
            json={
                "error": {
                    "code": 403,
                    "status": "PERMISSION_DENIED",
                    "message": "The caller does not have permission",
                    "details": [
                        {
                            "errors": [
                                {
                                    "errorCode": {"authorizationError": "DEVELOPER_TOKEN_NOT_APPROVED"},
                                    "message": "Developer token is not approved.",
                                }
                            ]
                        }
                    ],
                }
            },
        )

    client = _client(handler)
    with pytest.raises(GoogleAdsError) as excinfo:
        await client.search("SELECT campaign.id FROM campaign", customer_id="2222222222")

    message = str(excinfo.value)
    assert "DEVELOPER_TOKEN_NOT_APPROVED" in message
    assert "Basic access" in message  # the fix hint
    await client.aclose()


@pytest.mark.anyio
async def test_expired_refresh_token_explains_reauth():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"error": "invalid_grant", "error_description": "Token has been expired or revoked."}
        )

    client = _client(handler)
    with pytest.raises(AuthError, match="get_refresh_token.py"):
        await client.search("SELECT campaign.id FROM campaign", customer_id="2222222222")
    await client.aclose()


@pytest.mark.anyio
async def test_list_accessible_customers_strips_resource_prefix():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(
            200, json={"resourceNames": ["customers/1111111111", "customers/3333333333"]}
        )

    client = _client(handler)
    assert await client.list_accessible_customers() == ["1111111111", "3333333333"]
    await client.aclose()


# --------------------------------------------------------------------------
# Server wiring
# --------------------------------------------------------------------------


@pytest.mark.anyio
async def test_read_tools_are_registered():
    from viact_ads import server

    names = {tool.name for tool in await server.mcp.list_tools()}
    read_tools = {
        "check_connection",
        "list_accessible_customers",
        "list_managed_accounts",
        "list_negative_keywords",
        "account_summary",
        "campaign_performance",
        "ad_group_performance",
        "keyword_performance",
        "search_terms_report",
        "ad_performance",
        "run_gaql",
    }
    assert read_tools <= names, read_tools - names


@pytest.mark.anyio
async def test_read_tools_take_no_confirm_argument():
    """Only write tools gate on confirm; a read tool asking for it is a bug."""
    from viact_ads import server

    tools = {tool.name: tool for tool in await server.mcp.list_tools()}
    for name in ("campaign_performance", "search_terms_report", "run_gaql"):
        assert "confirm" not in tools[name].input_schema["properties"]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _config(default_customer_id: str | None = "1111111111") -> Config:
    return Config(
        developer_token="dev-token",
        client_id="client-id",
        client_secret="client-secret",
        refresh_token="refresh-token",
        login_customer_id="1111111111",
        default_customer_id=default_customer_id,
        api_version="v25",
    )


def _client(handler) -> GoogleAdsClient:
    client = GoogleAdsClient(_config())
    client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client._tokens._http = client._http
    return client
