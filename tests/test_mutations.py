"""Tests for the write path.

Nothing here touches a real account: the API is stubbed with
httpx.MockTransport. The point is to pin down the operation payloads, the
validateOnly gate, and the argument checks that stop a bad write leaving
the process.
"""

from __future__ import annotations

import httpx
import pytest

from viact_ads import mutations
from viact_ads.client import GoogleAdsClient, GoogleAdsError
from viact_ads.config import Config


# --------------------------------------------------------------------------
# Helpers and conversions
# --------------------------------------------------------------------------


def test_to_camel_matches_proto3_json_field_masks():
    assert mutations.to_camel("cost_micros") == "costMicros"
    assert mutations.to_camel("amount_micros") == "amountMicros"
    assert mutations.to_camel("status") == "status"


def test_money_crosses_the_boundary_in_currency_units():
    assert mutations.to_micros(175.0) == 175_000_000
    assert mutations.to_micros(8.5) == 8_500_000
    assert mutations.from_micros("175000000") == 175.0


def test_negative_money_is_rejected():
    with pytest.raises(mutations.MutationError, match="cannot be negative"):
        mutations.to_micros(-5, "daily_amount")


# --------------------------------------------------------------------------
# Status changes
# --------------------------------------------------------------------------


def test_set_status_builds_update_with_field_mask():
    service, operations = mutations.set_status(
        "campaign", "3767588103", ["123", "456"], "paused"
    )
    assert service == "campaign"
    assert operations[0] == {
        "update": {
            "resourceName": "customers/3767588103/campaigns/123",
            "status": "PAUSED",
        },
        "updateMask": "status",
    }
    assert len(operations) == 2


def test_keyword_status_uses_composite_resource_name():
    _, operations = mutations.set_status(
        "keyword", "3767588103", ["111~222"], "PAUSED"
    )
    assert (
        operations[0]["update"]["resourceName"]
        == "customers/3767588103/adGroupCriteria/111~222"
    )


def test_keyword_status_rejects_bare_id():
    with pytest.raises(mutations.MutationError, match="adGroupId~id"):
        mutations.set_status("keyword", "3767588103", ["222"], "PAUSED")


def test_invalid_status_and_entity_type_are_rejected():
    with pytest.raises(mutations.MutationError, match="status must be"):
        mutations.set_status("campaign", "3767588103", ["1"], "DISABLED")
    with pytest.raises(mutations.MutationError, match="entity_type must be"):
        mutations.set_status("budget", "3767588103", ["1"], "PAUSED")


# --------------------------------------------------------------------------
# Negative keywords
# --------------------------------------------------------------------------


def test_campaign_negative_keywords_attach_to_the_campaign():
    service, operations = mutations.add_negative_keywords(
        "3767588103", ["free", "jobs"], "PHRASE", campaign_id="21001864293"
    )
    assert service == "campaign_criterion"
    assert operations[0]["create"] == {
        "campaign": "customers/3767588103/campaigns/21001864293",
        "keyword": {"text": "free", "matchType": "PHRASE"},
        "negative": True,
    }
    assert len(operations) == 2


def test_ad_group_negative_keywords_attach_to_the_ad_group():
    service, operations = mutations.add_negative_keywords(
        "3767588103", ["free"], "EXACT", ad_group_id="999"
    )
    assert service == "ad_group_criterion"
    assert operations[0]["create"]["adGroup"] == "customers/3767588103/adGroups/999"


def test_shared_criteria_removal_builds_composite_resource_names():
    service, operations = mutations.remove_shared_criteria(
        "3767588103", "12093570497", ["2407683029958", "913188274"]
    )
    assert service == "shared_criterion"
    assert operations == [
        {"remove": "customers/3767588103/sharedCriteria/12093570497~2407683029958"},
        {"remove": "customers/3767588103/sharedCriteria/12093570497~913188274"},
    ]


def test_shared_criteria_removal_rejects_empty_input():
    with pytest.raises(mutations.MutationError, match="must not be empty"):
        mutations.remove_shared_criteria("3767588103", "12093570497", [])


def test_shared_criteria_are_a_different_service_from_campaign_negatives():
    """The UI calls both 'negative keywords'; the API does not."""
    assert mutations.SERVICES["shared_criterion"] == "sharedCriteria"
    assert mutations.SERVICES["campaign_criterion"] == "campaignCriteria"


def test_negative_keywords_need_exactly_one_parent():
    with pytest.raises(mutations.MutationError, match="exactly one"):
        mutations.add_negative_keywords("3767588103", ["free"], "PHRASE")
    with pytest.raises(mutations.MutationError, match="exactly one"):
        mutations.add_negative_keywords(
            "3767588103", ["free"], "PHRASE", campaign_id="1", ad_group_id="2"
        )


def test_blank_keywords_are_dropped_and_empty_lists_rejected():
    _, operations = mutations.add_negative_keywords(
        "3767588103", ["free", "  ", ""], "PHRASE", campaign_id="1"
    )
    assert len(operations) == 1
    with pytest.raises(mutations.MutationError, match="must not be empty"):
        mutations.add_negative_keywords("3767588103", ["  "], "PHRASE", campaign_id="1")


# --------------------------------------------------------------------------
# Budgets and bids
# --------------------------------------------------------------------------


def test_budget_update_converts_to_micros_with_matching_mask():
    service, operations = mutations.update_budget("3767588103", "13352364204", 200.0)
    assert service == "campaign_budget"
    assert operations[0] == {
        "update": {
            "resourceName": "customers/3767588103/campaignBudgets/13352364204",
            "amountMicros": "200000000",
        },
        "updateMask": "amountMicros",
    }


def test_target_cpa_requires_a_target():
    with pytest.raises(mutations.MutationError, match="needs target_value"):
        mutations.update_bidding_strategy("3767588103", "123", "TARGET_CPA")


def test_target_cpa_nests_the_mask():
    _, operations = mutations.update_bidding_strategy(
        "3767588103", "123", "TARGET_CPA", 172.0
    )
    assert operations[0]["updateMask"] == "targetCpa.targetCpaMicros"
    assert operations[0]["update"]["targetCpa"] == {"targetCpaMicros": "172000000"}


def test_target_roas_passes_a_ratio_not_micros():
    _, operations = mutations.update_bidding_strategy(
        "3767588103", "123", "TARGET_ROAS", 2.5
    )
    assert operations[0]["update"]["targetRoas"] == {"targetRoas": 2.5}


# --------------------------------------------------------------------------
# Creation
# --------------------------------------------------------------------------


def test_new_campaigns_default_to_paused():
    _, operations = mutations.create_campaign(
        "3767588103", "HK_Test", "customers/3767588103/campaignBudgets/1"
    )
    assert operations[0]["create"]["status"] == "PAUSED"


def test_campaign_dates_are_compacted():
    _, operations = mutations.create_campaign(
        "3767588103",
        "HK_Test",
        "customers/3767588103/campaignBudgets/1",
        start_date="2026-09-01",
        end_date="2026-09-30",
    )
    assert operations[0]["create"]["startDate"] == "20260901"
    assert operations[0]["create"]["endDate"] == "20260930"


def test_malformed_campaign_date_is_rejected():
    with pytest.raises(mutations.MutationError, match="YYYY-MM-DD"):
        mutations.create_campaign(
            "3767588103", "x", "customers/3767588103/campaignBudgets/1",
            start_date="01/09/2026",
        )


def test_responsive_search_ad_enforces_google_limits():
    good_headlines = ["AI Site Safety", "Cut Incidents 40%", "Book A Demo"]
    good_descriptions = ["Detect hazards in real time.", "Trusted on 100+ sites."]

    _, operations = mutations.create_responsive_search_ad(
        "3767588103", "999", good_headlines, good_descriptions, "https://viact.ai"
    )
    ad = operations[0]["create"]["ad"]
    assert ad["finalUrls"] == ["https://viact.ai"]
    assert len(ad["responsiveSearchAd"]["headlines"]) == 3

    with pytest.raises(mutations.MutationError, match="3-15 headlines"):
        mutations.create_responsive_search_ad(
            "3767588103", "999", ["only", "two"], good_descriptions, "https://viact.ai"
        )
    with pytest.raises(mutations.MutationError, match="2-4 descriptions"):
        mutations.create_responsive_search_ad(
            "3767588103", "999", good_headlines, ["one"], "https://viact.ai"
        )
    with pytest.raises(mutations.MutationError, match="over 30 characters"):
        mutations.create_responsive_search_ad(
            "3767588103",
            "999",
            ["x" * 31, "ok", "fine"],
            good_descriptions,
            "https://viact.ai",
        )
    with pytest.raises(mutations.MutationError, match="full URL"):
        mutations.create_responsive_search_ad(
            "3767588103", "999", good_headlines, good_descriptions, "viact.ai"
        )


# --------------------------------------------------------------------------
# Offline conversions
# --------------------------------------------------------------------------


def test_click_conversions_require_an_identifier():
    """A click id or a hashed email. Neither is an error; two click ids are too."""
    with pytest.raises(mutations.MutationError, match="needs a click identifier"):
        mutations.build_click_conversions(
            "3767588103", "555", [{"conversion_date_time": "2026-08-01 14:30:00+08:00"}]
        )
    with pytest.raises(mutations.MutationError, match="more than one click identifier"):
        mutations.build_click_conversions(
            "3767588103",
            "555",
            [{"gclid": "a", "wbraid": "b", "conversion_date_time": "2026-08-01 14:30:00+08:00"}],
        )


def test_click_conversion_datetime_format_is_enforced():
    with pytest.raises(mutations.MutationError, match="expected"):
        mutations.build_click_conversions(
            "3767588103", "555", [{"gclid": "abc", "conversion_date_time": "2026-08-01"}]
        )


def test_click_conversion_payload_shape():
    built = mutations.build_click_conversions(
        "3767588103",
        "555",
        [
            {
                "gclid": "abc123",
                "conversion_date_time": "2026-08-01 14:30:00+08:00",
                "conversion_value": 5000,
                "currency_code": "HKD",
            }
        ],
    )
    assert built[0] == {
        "conversionAction": "customers/3767588103/conversionActions/555",
        "conversionDateTime": "2026-08-01 14:30:00+08:00",
        "gclid": "abc123",
        "conversionValue": 5000.0,
        "currencyCode": "HKD",
    }


# --------------------------------------------------------------------------
# The validateOnly gate
# --------------------------------------------------------------------------


@pytest.mark.anyio
async def test_preview_sends_validate_only_and_apply_does_not():
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        import json as _json

        seen.append({"url": str(request.url), "body": _json.loads(request.content)})
        return httpx.Response(200, json={"results": [{"resourceName": "customers/1/campaigns/2"}]})

    client = _client(handler)
    _, operations = mutations.set_status("campaign", "3767588103", ["2"], "PAUSED")

    await client.mutate("campaign", operations, "3767588103", validate_only=True)
    assert seen[-1]["body"]["validateOnly"] is True
    assert seen[-1]["url"].endswith("/customers/3767588103/campaigns:mutate")
    # partialFailure must stay off during validation, or Google reports row
    # errors instead of rejecting the request outright.
    assert seen[-1]["body"]["partialFailure"] is False

    await client.mutate("campaign", operations, "3767588103", validate_only=False)
    assert seen[-1]["body"]["validateOnly"] is False
    assert seen[-1]["body"]["partialFailure"] is True

    await client.aclose()


@pytest.mark.anyio
async def test_partial_failure_is_raised_not_silently_returned():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(
            200,
            json={
                "results": [],
                "partialFailureError": {
                    "message": "one or more operations failed",
                    "details": [
                        {
                            "errors": [
                                {
                                    "errorCode": {"criterionError": "KEYWORD_HAS_INVALID_CHARS"},
                                    "message": "Keyword contains invalid characters.",
                                    "location": {
                                        "fieldPathElements": [
                                            {"fieldName": "operations", "index": 1}
                                        ]
                                    },
                                }
                            ]
                        }
                    ],
                },
            },
        )

    client = _client(handler)
    with pytest.raises(GoogleAdsError) as excinfo:
        await client.mutate("campaign", [{"remove": "x"}], "3767588103", validate_only=False)

    message = str(excinfo.value)
    assert "KEYWORD_HAS_INVALID_CHARS" in message
    assert "operation 1" in message
    await client.aclose()


@pytest.mark.anyio
async def test_offline_conversion_upload_hits_the_right_endpoint():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"results": [{}]})

    client = _client(handler)
    payload = mutations.build_click_conversions(
        "3767588103", "555",
        [{"gclid": "abc", "conversion_date_time": "2026-08-01 14:30:00+08:00"}],
    )
    await client.upload_click_conversions(payload, "3767588103", validate_only=True)
    assert seen["url"].endswith("/customers/3767588103:uploadClickConversions")
    await client.aclose()


# --------------------------------------------------------------------------
# Server wiring
# --------------------------------------------------------------------------


@pytest.mark.anyio
async def test_every_write_tool_defaults_to_preview():
    """A write tool whose confirm defaulted to true would apply silently."""
    from viact_ads import server

    write_tools = {
        "set_status",
        "add_negative_keywords",
        "remove_negative_keywords",
        "update_campaign_budget",
        "create_campaign_budget",
        "update_bid",
        "update_bidding_strategy",
        "create_campaign",
        "create_ad_group",
        "create_responsive_search_ad",
        "add_keywords",
        "upload_offline_conversions",
        "remove_shared_negative_keywords",
        "rename_entities",
    }

    tools = {tool.name: tool for tool in await server.mcp.list_tools()}
    assert write_tools <= set(tools), write_tools - set(tools)

    for name in write_tools:
        schema = tools[name].input_schema
        confirm = schema["properties"]["confirm"]
        assert confirm.get("default") is False, f"{name} does not default to preview"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _client(handler) -> GoogleAdsClient:
    config = Config(
        developer_token="dev-token",
        client_id="client-id",
        client_secret="client-secret",
        refresh_token="refresh-token",
        login_customer_id="7762289364",
        default_customer_id="3767588103",
        api_version="v25",
    )
    client = GoogleAdsClient(config)
    client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client._tokens._http = client._http
    return client


# --------------------------------------------------------------------------
# Renaming
# --------------------------------------------------------------------------


def test_rename_builds_name_update_with_mask():
    service, operations = mutations.rename(
        "ad_group", "3767588103", [("183774414699", "PPE Detection")]
    )
    assert service == "ad_group"
    assert operations[0] == {
        "update": {
            "resourceName": "customers/3767588103/adGroups/183774414699",
            "name": "PPE Detection",
        },
        "updateMask": "name",
    }


def test_rename_asset_group_uses_its_own_service():
    service, operations = mutations.rename(
        "asset_group", "3767588103", [("6546863961", "Smart Site Safety System")]
    )
    assert service == "asset_group"
    assert (
        operations[0]["update"]["resourceName"]
        == "customers/3767588103/assetGroups/6546863961"
    )


def test_campaigns_cannot_be_renamed():
    """Campaign names are referenced by reports and UTMs — renaming breaks them."""
    with pytest.raises(mutations.MutationError, match="deliberately excluded"):
        mutations.rename("campaign", "3767588103", [("123", "New Name")])


def test_rename_rejects_empty_and_duplicate_input():
    with pytest.raises(mutations.MutationError, match="must not be empty"):
        mutations.rename("ad_group", "3767588103", [])
    with pytest.raises(mutations.MutationError, match="Empty new name"):
        mutations.rename("ad_group", "3767588103", [("1", "   ")])
    with pytest.raises(mutations.MutationError, match="Duplicate entity id"):
        mutations.rename("ad_group", "3767588103", [("1", "A"), ("1", "B")])


def test_keyword_insertion_measures_default_text_not_the_macro():
    """Google counts the default text; the {KeyWord:...} wrapper does not count.

    The account runs an approved ad whose headline is 34 characters as written
    and 24 as its default text, so measuring the whole string rejects copy
    Google accepts.
    """
    assert mutations.effective_length("{KeyWord:Smart Site Safety System}") == 24
    assert mutations.effective_length("{keyword:PPE Detection}") == 13
    assert mutations.effective_length("Plain headline") == 14

    headlines = ["{KeyWord:Smart Site Safety System}", "CITF Listed 4S Platform",
                 "Multi-Site Safety Control"]
    _, operations = mutations.create_responsive_search_ad(
        "3767588103", "999", headlines,
        ["Description one text here.", "Description two text here."],
        "https://www.viact.ai/smart-site-safety-system")
    texts = [h["text"] for h in
             operations[0]["create"]["ad"]["responsiveSearchAd"]["headlines"]]
    assert texts[0] == "{KeyWord:Smart Site Safety System}"


def test_keyword_insertion_with_over_long_default_is_still_rejected():
    with pytest.raises(mutations.MutationError, match="over 30 characters"):
        mutations.create_responsive_search_ad(
            "3767588103", "999",
            ["{KeyWord:" + "x" * 31 + "}", "ok headline", "another headline"],
            ["Description one.", "Description two."],
            "https://www.viact.ai/")


@pytest.mark.asyncio
async def test_conversion_upload_always_sets_partial_failure_even_in_preview():
    """Google rejects uploadClickConversions outright without it.

    Unlike the generic mutate endpoints, this one requires partialFailure on
    every call - a preview with it off comes back PARTIAL_FAILURE_MODE_REQUIRED
    before any row is looked at.
    """
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        if "oauth2" in str(request.url):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        import json as _json
        seen.append(_json.loads(request.content))
        return httpx.Response(200, json={"results": []})

    client = _client(handler)
    await client.upload_click_conversions(
        [{"gclid": "x", "conversionDateTime": "2026-08-01 08:30:00+08:00"}],
        validate_only=True,
    )
    await client.aclose()
    assert seen[-1]["validateOnly"] is True
    assert seen[-1]["partialFailure"] is True
