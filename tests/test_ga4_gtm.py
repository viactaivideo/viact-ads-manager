"""Tests for the GA4 and Tag Manager modules. No network: httpx is stubbed."""

from __future__ import annotations

import httpx
import pytest

from viact_ads import ga4, gtm
from viact_ads.config import Config
from viact_ads.google_api import GoogleApiClient, GoogleApiError


# --------------------------------------------------------------------------
# GA4 argument handling
# --------------------------------------------------------------------------


def test_ga4_date_presets_and_explicit_ranges():
    assert ga4.date_range("LAST_30_DAYS") == {"startDate": "30daysAgo", "endDate": "yesterday"}
    assert ga4.date_range("last_7_days") == {"startDate": "7daysAgo", "endDate": "yesterday"}
    assert ga4.date_range("2026-07-01,2026-07-31") == {
        "startDate": "2026-07-01", "endDate": "2026-07-31"}


def test_ga4_rejects_bad_date_range():
    with pytest.raises(ValueError, match="Unrecognised date_range"):
        ga4.date_range("last month or so")
    with pytest.raises(ValueError, match="is after end"):
        ga4.date_range("2026-08-31,2026-08-01")


def test_ga4_property_id_strips_formatting(monkeypatch):
    assert ga4.property_id("252020859") == "252020859"
    assert ga4.property_id("properties/252020859") == "252020859"
    monkeypatch.setenv("GA4_PROPERTY_ID", " 252020859 ")
    assert ga4.property_id() == "252020859"


def test_ga4_flatten_pairs_headers_with_values():
    payload = {
        "dimensionHeaders": [{"name": "sessionSource"}, {"name": "sessionMedium"}],
        "metricHeaders": [{"name": "sessions"}, {"name": "engagementRate"}],
        "rows": [{
            "dimensionValues": [{"value": "google"}, {"value": "cpc"}],
            "metricValues": [{"value": "412"}, {"value": "0.6134"}],
        }],
    }
    assert ga4.flatten_report(payload) == [
        {"sessionSource": "google", "sessionMedium": "cpc",
         "sessions": 412, "engagementRate": 0.6134}]


# --------------------------------------------------------------------------
# GTM identifier handling
# --------------------------------------------------------------------------


def test_gtm_account_id_strips_formatting():
    assert gtm.account_id("6004059267") == "6004059267"
    assert gtm.account_id("accounts/6004059267") == "6004059267"


@pytest.mark.anyio
async def test_gtm_resolves_public_id_to_numeric_container_id():
    """GTM-XXXX is the website snippet ID; the API needs the numeric one."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        return httpx.Response(200, json={"container": [
            {"containerId": "98765432", "publicId": "GTM-MB6W3RC", "name": "viact.ai"},
            {"containerId": "11111111", "publicId": "GTM-OTHER01", "name": "other"},
        ]})

    client = _api(handler)
    account, container = await gtm.GTMClient(client).resolve_container(
        "GTM-MB6W3RC", "6004059267")
    assert (account, container) == ("6004059267", "98765432")
    await client.aclose()


@pytest.mark.anyio
async def test_gtm_accepts_a_numeric_container_id_without_a_lookup():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        raise AssertionError("a numeric container id must not trigger a lookup")

    client = _api(handler)
    assert await gtm.GTMClient(client).resolve_container("98765432", "6004059267") == (
        "6004059267", "98765432")
    await client.aclose()


@pytest.mark.anyio
async def test_gtm_unknown_public_id_lists_what_it_found():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        return httpx.Response(200, json={"container": [
            {"containerId": "98765432", "publicId": "GTM-REAL01"}]})

    client = _api(handler)
    with pytest.raises(ValueError, match="GTM-REAL01"):
        await gtm.GTMClient(client).resolve_container("GTM-NOPE99", "6004059267")
    await client.aclose()


# --------------------------------------------------------------------------
# Error translation
# --------------------------------------------------------------------------


@pytest.mark.anyio
async def test_missing_scope_error_explains_that_tokens_are_fixed_at_issue():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        return httpx.Response(403, json={"error": {
            "code": 403, "status": "PERMISSION_DENIED",
            "message": "Request had insufficient authentication scopes."}})

    client = _api(handler)
    with pytest.raises(GoogleApiError) as excinfo:
        await ga4.GA4Client(client).key_events("252020859")
    assert "Re-mint" in str(excinfo.value)
    await client.aclose()


@pytest.mark.anyio
async def test_ga4_report_returns_flattened_rows():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        assert request.url.path.endswith("/properties/252020859:runReport")
        return httpx.Response(200, json={
            "dimensionHeaders": [{"name": "landingPage"}],
            "metricHeaders": [{"name": "sessions"}],
            "rowCount": 1,
            "rows": [{"dimensionValues": [{"value": "/smart-site-safety-system"}],
                      "metricValues": [{"value": "128"}]}]})

    client = _api(handler)
    out = await ga4.GA4Client(client).run_report(
        ["landingPage"], ["sessions"], "LAST_30_DAYS", "252020859")
    assert out["rows"] == [{"landingPage": "/smart-site-safety-system", "sessions": 128}]
    assert out["property_id"] == "252020859"
    await client.aclose()


# --------------------------------------------------------------------------
# Server wiring
# --------------------------------------------------------------------------


@pytest.mark.anyio
async def test_ga4_and_gtm_tools_are_registered():
    from viact_ads import server

    names = {t.name for t in await server.mcp.list_tools()}
    expected = {
        "google_check_scopes", "ga4_key_events", "ga4_data_streams",
        "ga4_google_ads_links", "ga4_report", "ga4_conversions_by_source",
        "ga4_landing_page_performance", "ga4_event_counts",
        "gtm_containers", "gtm_tags", "gtm_triggers", "gtm_variables",
    }
    assert expected <= names, expected - names


@pytest.mark.anyio
async def test_no_gtm_write_tools_are_exposed():
    """Publishing a GTM container changes the live website, so no write tools."""
    from viact_ads import server

    names = {t.name for t in await server.mcp.list_tools()}
    assert not {n for n in names
                if n.startswith("gtm_")
                and any(w in n for w in ("create", "update", "publish", "delete"))}


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _api(handler) -> GoogleApiClient:
    config = Config(
        developer_token="dev", client_id="cid", client_secret="secret",
        refresh_token="refresh", login_customer_id="7762289364",
        default_customer_id="3767588103", api_version="v25")
    client = GoogleApiClient(config)
    client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client._tokens._http = client._http
    return client
