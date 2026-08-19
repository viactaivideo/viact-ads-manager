"""Tests for the Pipedrive bridge. No network: httpx is stubbed."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from viact_ads import bridge, mutations, pipedrive
from viact_ads.pipedrive import Deal, PipedriveClient, PipedriveError

NOW = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)


def make_deal(**kw) -> Deal:
    base = dict(
        id=1, title="Acme DC", status="won", stage_id=3, value=50000.0,
        currency="HKD", add_time="2026-08-01 09:00:00", won_time=None,
        update_time=None, email="Buyer@Example.com", gclid=None,
    )
    base.update(kw)
    return Deal(**base)


# ---------------------------------------------------------------- email hashing
def test_email_is_normalised_before_hashing():
    assert pipedrive.normalize_email("  Buyer@Example.COM ") == "buyer@example.com"


def test_gmail_dots_and_plus_tags_are_stripped():
    assert pipedrive.normalize_email("First.Last+ads@gmail.com") == "firstlast@gmail.com"
    # non-Gmail domains keep dots, because they are significant there
    assert pipedrive.normalize_email("first.last@viact.ai") == "first.last@viact.ai"


def test_hash_is_sha256_hex_of_the_normalised_address():
    digest = pipedrive.hash_email(" BUYER@example.com ")
    assert len(digest) == 64 and digest == pipedrive.hash_email("buyer@example.com")


def test_bad_email_is_rejected():
    with pytest.raises(PipedriveError, match="Not an email"):
        pipedrive.hash_email("not-an-address")


# ---------------------------------------------------------------- age filtering
def test_click_id_inside_ninety_days_uploads():
    deal = make_deal(gclid="Cj0ABC", add_time=(NOW - timedelta(days=80)).isoformat())
    out = bridge.prepare([deal], now=NOW)
    assert len(out.ready) == 1 and out.ready[0]["gclid"] == "Cj0ABC"


def test_click_id_past_ninety_days_is_skipped_not_sent():
    deal = make_deal(gclid="Cj0ABC", email=None,
                     add_time=(NOW - timedelta(days=95)).isoformat())
    out = bridge.prepare([deal], now=NOW)
    assert out.ready == []
    assert "too old" in out.skipped()[0].skip_reason


def test_email_route_cuts_off_at_sixty_three_days_not_ninety():
    """Enhanced conversions for leads has a shorter window than a click id."""
    inside = make_deal(id=1, add_time=(NOW - timedelta(days=60)).isoformat())
    outside = make_deal(id=2, add_time=(NOW - timedelta(days=70)).isoformat())
    out = bridge.prepare([inside, outside], now=NOW)
    assert len(out.ready) == 1
    assert out.ready[0]["hashed_email"] == pipedrive.hash_email("Buyer@Example.com")
    assert "63" in out.skipped()[0].skip_reason


def test_deal_with_neither_identifier_is_skipped():
    out = bridge.prepare([make_deal(email=None, gclid=None)], now=NOW)
    assert out.ready == []
    assert "no click id and no email" in out.skipped()[0].skip_reason


def test_click_id_is_preferred_over_email_when_both_present():
    deal = make_deal(gclid="Cj0ABC", add_time=(NOW - timedelta(days=70)).isoformat())
    out = bridge.prepare([deal], now=NOW)
    assert "gclid" in out.ready[0] and "hashed_email" not in out.ready[0]


def test_duplicate_deal_ids_are_only_sent_once():
    d = make_deal()
    out = bridge.prepare([d, d], now=NOW)
    assert len(out.ready) == 1
    assert "duplicate" in out.skipped()[0].skip_reason


# ---------------------------------------------------------------- values
def test_lost_deals_upload_at_zero_so_bidding_learns_what_to_avoid():
    won = make_deal(id=1, status="won")
    lost = make_deal(id=2, status="lost")
    out = bridge.prepare([won, lost], now=NOW,
                         value_map={"won": 100.0, "lost": 0.0})
    values = sorted(c["conversion_value"] for c in out.ready)
    assert values == [0.0, 100.0]


def test_order_id_is_derived_from_the_deal_so_reuploads_do_not_double_count():
    out = bridge.prepare([make_deal(id=77)], now=NOW)
    assert out.ready[0]["order_id"] == "pd-77"


def test_conversion_time_is_formatted_in_the_account_timezone():
    out = bridge.prepare([make_deal(add_time="2026-08-01T00:30:00+00:00")],
                         now=NOW, tz_offset="+08:00")
    assert out.ready[0]["conversion_date_time"] == "2026-08-01 08:30:00+08:00"


# ---------------------------------------------------------------- payload shape
def test_hashed_email_becomes_a_user_identifier_for_google():
    built = mutations.build_click_conversions(
        "3767588103", "999",
        [{"hashed_email": pipedrive.hash_email("buyer@example.com"),
          "conversion_date_time": "2026-08-01 08:30:00+08:00"}],
    )
    assert built[0]["userIdentifiers"] == [
        {"hashedEmail": pipedrive.hash_email("buyer@example.com")}]


def test_unhashed_email_is_refused():
    with pytest.raises(mutations.MutationError, match="SHA-256"):
        mutations.build_click_conversions(
            "3767588103", "999",
            [{"hashed_email": "buyer@example.com",
              "conversion_date_time": "2026-08-01 08:30:00+08:00"}],
        )


def test_conversion_without_any_identifier_is_refused():
    with pytest.raises(mutations.MutationError, match="needs a click identifier"):
        mutations.build_click_conversions(
            "3767588103", "999",
            [{"conversion_date_time": "2026-08-01 08:30:00+08:00"}],
        )


# ---------------------------------------------------------------- Pipedrive API
def _client(handler) -> PipedriveClient:
    return PipedriveClient(token="tok", host="https://api.pipedrive.com",
                           transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_token_travels_in_the_header_never_the_url():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["header"] = request.headers.get("x-api-token")
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"success": True, "data": []})

    c = _client(handler)
    await c.deals()
    await c.aclose()
    assert seen["header"] == "tok"
    assert "api_token" not in seen["url"]


@pytest.mark.asyncio
async def test_custom_field_is_resolved_by_name_not_hardcoded():
    """Pipedrive keys custom fields by a per-account hash, so it must be looked up."""
    key = "a" * 40

    def handler(request: httpx.Request) -> httpx.Response:
        if "dealFields" in request.url.path:
            return httpx.Response(200, json={"success": True, "data": [
                {"name": "GCLID", "key": key}]})
        return httpx.Response(200, json={"success": True, "data": [
            {"id": 5, "title": "Acme", "status": "won",
             "add_time": "2026-08-01 09:00:00",
             "custom_fields": {key: "Cj0XYZ"},
             "person_id": {"email": [{"value": "b@example.com", "primary": True}]}}]})

    c = _client(handler)
    deals = await c.deals(gclid_field="GCLID")
    await c.aclose()
    assert deals[0].gclid == "Cj0XYZ" and deals[0].email == "b@example.com"


@pytest.mark.asyncio
async def test_rate_limit_explains_the_daily_budget():
    c = _client(lambda r: httpx.Response(429, json={}))
    with pytest.raises(PipedriveError, match="daily token budget"):
        await c.deals()
    await c.aclose()


@pytest.mark.asyncio
async def test_bad_token_is_explained():
    c = _client(lambda r: httpx.Response(401, json={}))
    with pytest.raises(PipedriveError, match="rejected the API token"):
        await c.deals()
    await c.aclose()


def test_missing_token_names_where_to_get_one(monkeypatch):
    monkeypatch.delenv("PIPEDRIVE_API_TOKEN", raising=False)
    with pytest.raises(PipedriveError, match="Personal preferences"):
        pipedrive.api_token()


@pytest.mark.asyncio
async def test_v2_person_id_is_an_integer_so_the_email_needs_a_second_lookup():
    """The bug that skipped every real deal: v2 does not inline person email."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if "persons" in request.url.path:
            return httpx.Response(200, json={"success": True, "data": [
                {"id": 42, "emails": [{"value": "buyer@acme.com", "primary": True}]},
            ]})
        return httpx.Response(200, json={"success": True, "data": [
            {"id": 7, "title": "Acme", "status": "won", "person_id": 42,
             "add_time": "2026-08-01 09:00:00"},
        ]})

    c = _client(handler)
    deals = await c.deals()
    await c.aclose()
    assert deals[0].email == "buyer@acme.com"
    assert any("persons" in p for p in calls), "should have looked the person up"


@pytest.mark.asyncio
async def test_person_lookup_is_skipped_when_no_deal_needs_it():
    """One address-book pass per batch at most, and none when it buys nothing."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"success": True, "data": [
            {"id": 7, "title": "Acme", "status": "won", "person_id": None,
             "add_time": "2026-08-01 09:00:00"},
        ]})

    c = _client(handler)
    await c.deals()
    await c.aclose()
    assert not any("persons" in p for p in calls)

