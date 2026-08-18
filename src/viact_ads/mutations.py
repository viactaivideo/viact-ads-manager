"""Operation builders for the Google Ads mutate endpoints.

Every builder returns a plain dict in Google's operation shape. Nothing here
talks to the network — the client sends these, and sends them with
validateOnly first so a change can be previewed before it is applied.

Two conventions worth knowing:

* Money crosses this module's public surface in **currency units** (175.0),
  not micros. Callers should never have to write 175000000 and count zeros.
* `updateMask` must list exactly the fields an update touches, in the camelCase
  form proto3 JSON uses. It is derived from the payload rather than written out
  by hand, so the two cannot drift apart.
"""

from __future__ import annotations

import re
from typing import Any

_SNAKE_BOUNDARY = re.compile(r"_([a-z0-9])")

# Logical name -> path segment on /customers/{id}/
SERVICES = {
    "campaign": "campaigns",
    "ad_group": "adGroups",
    "ad_group_criterion": "adGroupCriteria",
    "campaign_criterion": "campaignCriteria",
    "ad_group_ad": "adGroupAds",
    "campaign_budget": "campaignBudgets",
    # Shared exclusion lists under Shared Library. Their criteria are addressed
    # as sharedSetId~criterionId, and are a different service from the
    # campaign-level negatives even though the UI presents both as "negatives".
    "shared_criterion": "sharedCriteria",
    # Performance Max holds its creative in asset groups rather than ad groups.
    "asset_group": "assetGroups",
    # AdService edits the ad itself (URLs, tracking). Distinct from
    # adGroupAds, which only governs the ad's link to its ad group.
    "ad": "ads",
    # Performance Max creative is a set of links between an asset group and
    # account-level assets, so adding a headline means linking an asset rather
    # than editing text in place.
    "asset": "assets",
    "asset_group_asset": "assetGroupAssets",
    # Extension assets (sitelinks, callouts, snippets) attach at three levels.
    # The link is what carries the status, so detaching one is a remove on the
    # link, never on the shared asset it points at.
    "customer_asset": "customerAssets",
    "campaign_asset": "campaignAssets",
    "ad_group_asset": "adGroupAssets",
}

# Levels that can carry a final URL suffix. Google applies only the most
# specific one — they do not concatenate.
SUFFIX_LEVELS = ("campaign", "ad_group", "ad")

# Levels whose final URLs can be rewritten.
URL_LEVELS = ("ad", "asset_group")

# What `rename` will act on. Campaigns are deliberately absent: renaming one
# breaks every report, saved filter and UTM already pointing at its name.
RENAMEABLE = ("ad_group", "asset_group")

# What `set_status` can act on, and how to address each one.
STATUS_TARGETS = {
    "campaign": "campaign",
    "ad_group": "ad_group",
    "keyword": "ad_group_criterion",
    "ad": "ad_group_ad",
}

VALID_STATUSES = ("ENABLED", "PAUSED", "REMOVED")

MATCH_TYPES = ("EXACT", "PHRASE", "BROAD")

BIDDING_STRATEGIES = {
    "MANUAL_CPC": "manualCpc",
    "MAXIMIZE_CONVERSIONS": "maximizeConversions",
    "MAXIMIZE_CONVERSION_VALUE": "maximizeConversionValue",
    "TARGET_CPA": "targetCpa",
    "TARGET_ROAS": "targetRoas",
    "TARGET_SPEND": "targetSpend",
}

CHANNEL_TYPES = (
    "SEARCH",
    "DISPLAY",
    "SHOPPING",
    "VIDEO",
    "PERFORMANCE_MAX",
    "DEMAND_GEN",
)


class MutationError(ValueError):
    """Raised when mutation arguments cannot be turned into a valid operation."""


def to_camel(name: str) -> str:
    """cost_micros -> costMicros. Field masks and REST payloads both need this."""
    return _SNAKE_BOUNDARY.sub(lambda m: m.group(1).upper(), name)


def to_micros(amount: float, label: str = "amount") -> int:
    """Currency units -> micros, which is how Google stores money."""
    try:
        value = float(amount)
    except (TypeError, ValueError):
        raise MutationError(f"{label} must be a number, got {amount!r}.")
    if value < 0:
        raise MutationError(f"{label} cannot be negative, got {value}.")
    return int(round(value * 1_000_000))


def from_micros(value: Any) -> float | None:
    try:
        return round(float(value) / 1_000_000, 4)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Resource names
# ---------------------------------------------------------------------------


def resource_name(service: str, customer_id: str, *ids: str | int) -> str:
    if service not in SERVICES:
        raise MutationError(f"Unknown service {service!r}.")
    # Composite IDs (ad group criteria, ads) are joined with a tilde.
    suffix = "~".join(str(i) for i in ids)
    return f"customers/{customer_id}/{SERVICES[service]}/{suffix}"


def _update(payload: dict[str, Any], mask_fields: list[str]) -> dict[str, Any]:
    """Wrap a payload as an update operation with a matching field mask."""
    return {"update": payload, "updateMask": ",".join(mask_fields)}


# ---------------------------------------------------------------------------
# Status changes
# ---------------------------------------------------------------------------


def set_status(
    entity_type: str, customer_id: str, entity_ids: list[str], status: str
) -> tuple[str, list[dict]]:
    """Pause, enable, or remove campaigns, ad groups, keywords, or ads.

    Keywords and ads need a composite ID: "adGroupId~criterionId".
    Returns (service, operations).
    """
    if entity_type not in STATUS_TARGETS:
        raise MutationError(
            f"entity_type must be one of {', '.join(STATUS_TARGETS)} — got {entity_type!r}."
        )
    status = str(status).strip().upper()
    if status not in VALID_STATUSES:
        raise MutationError(
            f"status must be one of {', '.join(VALID_STATUSES)} — got {status!r}."
        )
    if not entity_ids:
        raise MutationError("entity_ids must not be empty.")

    service = STATUS_TARGETS[entity_type]
    operations = []
    for entity_id in entity_ids:
        parts = str(entity_id).split("~")
        if entity_type in ("keyword", "ad") and len(parts) != 2:
            raise MutationError(
                f"{entity_type} IDs must be 'adGroupId~id', got {entity_id!r}."
            )
        operations.append(
            _update(
                {
                    "resourceName": resource_name(service, customer_id, *parts),
                    "status": status,
                },
                ["status"],
            )
        )
    return service, operations


# ---------------------------------------------------------------------------
# Negative keywords
# ---------------------------------------------------------------------------


def add_negative_keywords(
    customer_id: str,
    keywords: list[str],
    match_type: str = "PHRASE",
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
) -> tuple[str, list[dict]]:
    """Block queries at campaign or ad group level."""
    match_type = str(match_type).strip().upper()
    if match_type not in MATCH_TYPES:
        raise MutationError(
            f"match_type must be one of {', '.join(MATCH_TYPES)} — got {match_type!r}."
        )
    if bool(campaign_id) == bool(ad_group_id):
        raise MutationError(
            "Give exactly one of campaign_id or ad_group_id — campaign level blocks "
            "the query across every ad group, ad group level only within one."
        )
    cleaned = [k.strip() for k in keywords if k and k.strip()]
    if not cleaned:
        raise MutationError("keywords must not be empty.")

    service = "campaign_criterion" if campaign_id else "ad_group_criterion"
    if campaign_id:
        parent = {"campaign": f"customers/{customer_id}/campaigns/{campaign_id}"}
    else:
        parent = {"adGroup": f"customers/{customer_id}/adGroups/{ad_group_id}"}

    operations = [
        {
            "create": {
                **parent,
                "keyword": {"text": text, "matchType": match_type},
                "negative": True,
            }
        }
        for text in cleaned
    ]
    return service, operations


def rename(
    entity_type: str, customer_id: str, renames: list[tuple[str, str]]
) -> tuple[str, list[dict]]:
    """Rename ad groups or asset groups.

    renames is a list of (entity_id, new_name). Campaigns are not renameable
    here by design — their names are referenced by reports, saved filters and
    UTM parameters that a rename would silently break.
    """
    if entity_type not in RENAMEABLE:
        raise MutationError(
            f"Only {' and '.join(RENAMEABLE)} can be renamed — got {entity_type!r}. "
            "Campaigns are deliberately excluded."
        )
    if not renames:
        raise MutationError("renames must not be empty.")

    seen: set[str] = set()
    operations = []
    for entity_id, new_name in renames:
        name = str(new_name).strip()
        if not name:
            raise MutationError(f"Empty new name for {entity_type} {entity_id}.")
        if len(name) > 255:
            raise MutationError(f"Name over 255 characters: {name!r}")
        if str(entity_id) in seen:
            raise MutationError(f"Duplicate entity id in renames: {entity_id}")
        seen.add(str(entity_id))
        operations.append(
            _update(
                {
                    "resourceName": resource_name(entity_type, customer_id, entity_id),
                    "name": name,
                },
                ["name"],
            )
        )
    return entity_type, operations


def set_final_url_suffix(
    entity_type: str, customer_id: str, pairs: list[tuple[str, str]]
) -> tuple[str, list[dict]]:
    """Set the final URL suffix on campaigns, ad groups, or ads.

    Only the most specific level in effect is applied by Google, so the suffix
    written here must be complete on its own rather than additive.
    """
    if entity_type not in SUFFIX_LEVELS:
        raise MutationError(
            f"A final URL suffix can only be set on {', '.join(SUFFIX_LEVELS)} — "
            f"got {entity_type!r}."
        )
    if not pairs:
        raise MutationError("pairs must not be empty.")

    operations = []
    for entity_id, suffix in pairs:
        text = str(suffix).strip().lstrip("?")
        if len(text) > 2048:
            raise MutationError(f"Suffix over 2048 characters for {entity_id}.")
        if text.startswith("&"):
            raise MutationError(f"Suffix must not start with '&': {text!r}")
        operations.append(
            _update(
                {
                    "resourceName": resource_name(entity_type, customer_id, entity_id),
                    "finalUrlSuffix": text,
                },
                ["finalUrlSuffix"],
            )
        )
    return entity_type, operations


def set_final_urls(
    entity_type: str, customer_id: str, pairs: list[tuple[str, list[str]]]
) -> tuple[str, list[dict]]:
    """Replace the final URLs on ads or asset groups.

    Changing an ad's URL sends it back through Google's policy review. The ad
    keeps its ID, so its history stays attached to it.
    """
    if entity_type not in URL_LEVELS:
        raise MutationError(
            f"Final URLs can only be rewritten on {', '.join(URL_LEVELS)} — "
            f"got {entity_type!r}."
        )
    if not pairs:
        raise MutationError("pairs must not be empty.")

    operations = []
    for entity_id, urls in pairs:
        cleaned = [str(u).strip() for u in urls if str(u).strip()]
        if not cleaned:
            raise MutationError(f"No final URLs given for {entity_id}.")
        for url in cleaned:
            if not url.startswith(("http://", "https://")):
                raise MutationError(f"Not a full URL: {url!r}")
        operations.append(
            _update(
                {
                    "resourceName": resource_name(entity_type, customer_id, entity_id),
                    "finalUrls": cleaned,
                },
                ["finalUrls"],
            )
        )
    return entity_type, operations


def remove_criteria(resource_names: list[str], service: str) -> tuple[str, list[dict]]:
    """Remove criteria (negative keywords, keywords) by full resource name."""
    if service not in ("campaign_criterion", "ad_group_criterion", "shared_criterion"):
        raise MutationError(f"Cannot remove criteria from service {service!r}.")
    if not resource_names:
        raise MutationError("resource_names must not be empty.")
    return service, [{"remove": name} for name in resource_names]


def remove_shared_criteria(
    customer_id: str, shared_set_id: str, criterion_ids: list[str]
) -> tuple[str, list[dict]]:
    """Remove terms from a shared exclusion list by criterion ID."""
    if not criterion_ids:
        raise MutationError("criterion_ids must not be empty.")
    if not str(shared_set_id).strip():
        raise MutationError("shared_set_id is required.")
    names = [
        resource_name("shared_criterion", customer_id, shared_set_id, criterion_id)
        for criterion_id in criterion_ids
    ]
    return remove_criteria(names, "shared_criterion")


# ---------------------------------------------------------------------------
# Budgets and bids
# ---------------------------------------------------------------------------


def update_budget(
    customer_id: str, budget_id: str, daily_amount: float
) -> tuple[str, list[dict]]:
    """Set a campaign budget's daily amount, in currency units."""
    return "campaign_budget", [
        _update(
            {
                "resourceName": resource_name("campaign_budget", customer_id, budget_id),
                "amountMicros": str(to_micros(daily_amount, "daily_amount")),
            },
            ["amountMicros"],
        )
    ]


def create_budget(
    customer_id: str, name: str, daily_amount: float, shared: bool = False
) -> tuple[str, list[dict]]:
    if not name or not name.strip():
        raise MutationError("Budget name is required.")
    return "campaign_budget", [
        {
            "create": {
                "name": name.strip(),
                "amountMicros": str(to_micros(daily_amount, "daily_amount")),
                "deliveryMethod": "STANDARD",
                "explicitlyShared": bool(shared),
            }
        }
    ]


def update_bid(
    entity_type: str, customer_id: str, entity_id: str, bid: float
) -> tuple[str, list[dict]]:
    """Set a max CPC bid on an ad group or a keyword."""
    micros = str(to_micros(bid, "bid"))
    if entity_type == "ad_group":
        return "ad_group", [
            _update(
                {
                    "resourceName": resource_name("ad_group", customer_id, entity_id),
                    "cpcBidMicros": micros,
                },
                ["cpcBidMicros"],
            )
        ]
    if entity_type == "keyword":
        parts = str(entity_id).split("~")
        if len(parts) != 2:
            raise MutationError(
                f"keyword IDs must be 'adGroupId~criterionId', got {entity_id!r}."
            )
        return "ad_group_criterion", [
            _update(
                {
                    "resourceName": resource_name(
                        "ad_group_criterion", customer_id, *parts
                    ),
                    "cpcBidMicros": micros,
                },
                ["cpcBidMicros"],
            )
        ]
    raise MutationError("entity_type for a bid must be 'ad_group' or 'keyword'.")


def update_bidding_strategy(
    customer_id: str,
    campaign_id: str,
    strategy: str,
    target_value: float | None = None,
) -> tuple[str, list[dict]]:
    """Switch a campaign's bidding strategy.

    target_value means CPA in currency units for TARGET_CPA, and a ratio for
    TARGET_ROAS (2.5 = 250% return). It is ignored by the others.
    """
    strategy = str(strategy).strip().upper()
    if strategy not in BIDDING_STRATEGIES:
        raise MutationError(
            f"strategy must be one of {', '.join(BIDDING_STRATEGIES)} — got {strategy!r}."
        )
    field = BIDDING_STRATEGIES[strategy]
    payload: dict[str, Any] = {
        "resourceName": resource_name("campaign", customer_id, campaign_id)
    }

    if strategy == "TARGET_CPA":
        if target_value is None:
            raise MutationError("TARGET_CPA needs target_value (a cost per acquisition).")
        payload[field] = {"targetCpaMicros": str(to_micros(target_value, "target_value"))}
        mask = [f"{field}.targetCpaMicros"]
    elif strategy == "TARGET_ROAS":
        if target_value is None:
            raise MutationError("TARGET_ROAS needs target_value (e.g. 2.5 for 250%).")
        payload[field] = {"targetRoas": float(target_value)}
        mask = [f"{field}.targetRoas"]
    elif strategy == "MANUAL_CPC":
        payload[field] = {"enhancedCpcEnabled": False}
        mask = [field]
    else:
        payload[field] = {}
        mask = [field]

    return "campaign", [_update(payload, mask)]


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


def create_campaign(
    customer_id: str,
    name: str,
    budget_resource_name: str,
    channel_type: str = "SEARCH",
    status: str = "PAUSED",
    strategy: str = "MANUAL_CPC",
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[str, list[dict]]:
    """Create a campaign. Defaults to PAUSED so nothing starts spending by accident."""
    if not name or not name.strip():
        raise MutationError("Campaign name is required.")
    channel_type = str(channel_type).strip().upper()
    if channel_type not in CHANNEL_TYPES:
        raise MutationError(
            f"channel_type must be one of {', '.join(CHANNEL_TYPES)} — got {channel_type!r}."
        )
    status = str(status).strip().upper()
    if status not in ("ENABLED", "PAUSED"):
        raise MutationError("A new campaign must start as ENABLED or PAUSED.")
    strategy = str(strategy).strip().upper()
    if strategy not in BIDDING_STRATEGIES:
        raise MutationError(f"Unknown bidding strategy {strategy!r}.")

    payload: dict[str, Any] = {
        "name": name.strip(),
        "status": status,
        "advertisingChannelType": channel_type,
        "campaignBudget": budget_resource_name,
        BIDDING_STRATEGIES[strategy]: {},
    }
    for field, value in (("startDate", start_date), ("endDate", end_date)):
        if value:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise MutationError(f"{field} must be YYYY-MM-DD, got {value!r}.")
            payload[field] = value.replace("-", "")
    return "campaign", [{"create": payload}]


def create_ad_group(
    customer_id: str,
    campaign_id: str,
    name: str,
    cpc_bid: float | None = None,
    status: str = "PAUSED",
) -> tuple[str, list[dict]]:
    if not name or not name.strip():
        raise MutationError("Ad group name is required.")
    status = str(status).strip().upper()
    if status not in ("ENABLED", "PAUSED"):
        raise MutationError("A new ad group must start as ENABLED or PAUSED.")
    payload: dict[str, Any] = {
        "name": name.strip(),
        "status": status,
        "campaign": f"customers/{customer_id}/campaigns/{campaign_id}",
        "type": "SEARCH_STANDARD",
    }
    if cpc_bid is not None:
        payload["cpcBidMicros"] = str(to_micros(cpc_bid, "cpc_bid"))
    return "ad_group", [{"create": payload}]


_KEYWORD_INSERTION = re.compile(r"^\{keyword:(.*)\}$", re.IGNORECASE | re.DOTALL)


def effective_length(text: str) -> int:
    """Length Google measures against the character limit.

    For keyword insertion, only the default text counts — the `{KeyWord:...}`
    wrapper does not. Measuring the whole string rejects headlines Google
    accepts, which is how this was found: the account already runs an approved
    ad whose headline is 34 characters written, 24 as its default text.
    """
    match = _KEYWORD_INSERTION.match(str(text).strip())
    return len(match.group(1)) if match else len(str(text))


def create_responsive_search_ad(
    customer_id: str,
    ad_group_id: str,
    headlines: list[str],
    descriptions: list[str],
    final_url: str,
    path1: str | None = None,
    path2: str | None = None,
    status: str = "PAUSED",
) -> tuple[str, list[dict]]:
    """Google requires 3-15 headlines (<=30 chars) and 2-4 descriptions (<=90)."""
    headlines = [h.strip() for h in headlines if h and h.strip()]
    descriptions = [d.strip() for d in descriptions if d and d.strip()]

    if not 3 <= len(headlines) <= 15:
        raise MutationError(
            f"Responsive search ads need 3-15 headlines, got {len(headlines)}."
        )
    if not 2 <= len(descriptions) <= 4:
        raise MutationError(
            f"Responsive search ads need 2-4 descriptions, got {len(descriptions)}."
        )
    for text in headlines:
        n = effective_length(text)
        if n > 30:
            raise MutationError(f"Headline over 30 characters ({n}): {text!r}")
    for text in descriptions:
        n = effective_length(text)
        if n > 90:
            raise MutationError(f"Description over 90 characters ({n}): {text!r}")
    if not final_url.startswith(("http://", "https://")):
        raise MutationError(f"final_url must be a full URL, got {final_url!r}.")

    ad: dict[str, Any] = {
        "finalUrls": [final_url],
        "responsiveSearchAd": {
            "headlines": [{"text": t} for t in headlines],
            "descriptions": [{"text": t} for t in descriptions],
        },
    }
    for key, value in (("path1", path1), ("path2", path2)):
        if value:
            if len(value) > 15:
                raise MutationError(f"{key} must be 15 characters or fewer.")
            ad["responsiveSearchAd"][key] = value

    return "ad_group_ad", [
        {
            "create": {
                "adGroup": f"customers/{customer_id}/adGroups/{ad_group_id}",
                "status": str(status).strip().upper(),
                "ad": ad,
            }
        }
    ]


def add_keywords(
    customer_id: str,
    ad_group_id: str,
    keywords: list[str],
    match_type: str = "PHRASE",
    bid: float | None = None,
) -> tuple[str, list[dict]]:
    match_type = str(match_type).strip().upper()
    if match_type not in MATCH_TYPES:
        raise MutationError(
            f"match_type must be one of {', '.join(MATCH_TYPES)} — got {match_type!r}."
        )
    cleaned = [k.strip() for k in keywords if k and k.strip()]
    if not cleaned:
        raise MutationError("keywords must not be empty.")

    operations = []
    for text in cleaned:
        payload: dict[str, Any] = {
            "adGroup": f"customers/{customer_id}/adGroups/{ad_group_id}",
            "status": "ENABLED",
            "keyword": {"text": text, "matchType": match_type},
        }
        if bid is not None:
            payload["cpcBidMicros"] = str(to_micros(bid, "bid"))
        operations.append({"create": payload})
    return "ad_group_criterion", operations


# ---------------------------------------------------------------------------
# Offline conversions
# ---------------------------------------------------------------------------

_CONVERSION_TIME = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$"
)


def build_click_conversions(
    customer_id: str,
    conversion_action_id: str,
    conversions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Shape offline conversions for :uploadClickConversions.

    Each entry needs a click identifier (gclid, gbraid, or wbraid) and a
    conversion_date_time as 'YYYY-MM-DD HH:MM:SS+HH:MM' in the account's
    timezone.
    """
    if not conversions:
        raise MutationError("conversions must not be empty.")

    action = f"customers/{customer_id}/conversionActions/{conversion_action_id}"
    built = []
    for index, entry in enumerate(conversions):
        identifiers = {k: entry.get(k) for k in ("gclid", "gbraid", "wbraid") if entry.get(k)}
        if len(identifiers) != 1:
            raise MutationError(
                f"Conversion {index} needs exactly one of gclid, gbraid, or wbraid; "
                f"got {list(identifiers) or 'none'}."
            )
        when = entry.get("conversion_date_time", "")
        if not _CONVERSION_TIME.match(str(when)):
            raise MutationError(
                f"Conversion {index} has conversion_date_time {when!r}; expected "
                f"'YYYY-MM-DD HH:MM:SS+HH:MM' (e.g. '2026-08-01 14:30:00+08:00')."
            )
        payload: dict[str, Any] = {
            "conversionAction": action,
            "conversionDateTime": when,
            **identifiers,
        }
        if entry.get("conversion_value") is not None:
            payload["conversionValue"] = float(entry["conversion_value"])
            payload["currencyCode"] = entry.get("currency_code", "HKD")
        if entry.get("order_id"):
            payload["orderId"] = str(entry["order_id"])
        built.append(payload)
    return built
