# -*- coding: utf-8 -*-
"""Every module/rule claim anywhere in the account, whatever the status."""
import asyncio, re
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config
RX=re.compile(r"\b\d+\s*\+?\s*(?:ai|smart|safety|pre-?built|in-?built|detection|vision)?\s*"
              r"(?:ai|smart|safety)?\s*(?:modules?|rules?|models?|use\s*cases?|scenarios?|"
              r"algorithms?|features?)\b", re.I)
CANON="200+ Safety Modules"
async def m():
    c=GoogleAdsClient(load_config())
    print("=== PMAX TEXT ASSETS (all statuses) ===")
    for x in await c.search("SELECT campaign.name, campaign.status, asset_group.name, asset_group.id, "
      "asset_group.status, asset_group_asset.field_type, asset_group_asset.status, asset.id, "
      "asset.text_asset.text FROM asset_group_asset WHERE asset_group_asset.status!='REMOVED'"):
        t=x.get("asset.text_asset.text") or ""
        if RX.search(t) and t!=CANON:
            print(f"  camp={x['campaign.status']:8} group={x['asset_group.status']:8} "
                  f"link={x['asset_group_asset.status']:8} {x['asset_group_asset.field_type']:14} "
                  f"asset {x['asset.id']}")
            print(f"      {x['campaign.name']} / {x['asset_group.name']} (group {x['asset_group.id']})")
            print(f"      {t}")
    print("\n=== SEARCH ADS (all statuses) ===")
    for a in await c.search("SELECT campaign.name, campaign.status, ad_group.name, ad_group.status, "
      "ad_group_ad.status, ad_group_ad.ad.id, ad_group_ad.ad.responsive_search_ad.headlines, "
      "ad_group_ad.ad.responsive_search_ad.descriptions FROM ad_group_ad "
      "WHERE ad_group_ad.status!='REMOVED'"):
        for f,lab in (("headlines","HEADLINE"),("descriptions","DESCRIPTION")):
            for i in a.get(f"ad_group_ad.ad.responsive_search_ad.{f}") or []:
                if RX.search(i["text"]) and i["text"]!=CANON and CANON not in i["text"]:
                    print(f"  camp={a['campaign.status']:8} group={a['ad_group.status']:8} "
                          f"ad={a['ad_group_ad.status']:8} {lab:12} ad {a['ad_group_ad.ad.id']}")
                    print(f"      {a['campaign.name']} / {a['ad_group.name']}")
                    print(f"      {i['text']}")
    print("\n=== EXTENSION ASSETS (all statuses) ===")
    for res in ("customer_asset","campaign_asset","ad_group_asset"):
        camp="campaign.name, campaign.status, " if res!="customer_asset" else ""
        ag="ad_group.name, ad_group.status, " if res=="ad_group_asset" else ""
        for x in await c.search(f"SELECT {camp}{ag}asset.id, asset.callout_asset.callout_text, "
          f"asset.sitelink_asset.link_text, asset.sitelink_asset.description1, "
          f"asset.sitelink_asset.description2, asset.structured_snippet_asset.values, "
          f"{res}.field_type, {res}.status FROM {res} WHERE {res}.status!='REMOVED'"):
            for v in ([x.get("asset.callout_asset.callout_text"),
                       x.get("asset.sitelink_asset.link_text"),
                       x.get("asset.sitelink_asset.description1"),
                       x.get("asset.sitelink_asset.description2")]
                      + (x.get("asset.structured_snippet_asset.values") or [])):
                if v and RX.search(v) and v!=CANON:
                    print(f"  {res:16} camp={x.get('campaign.status','-'):8} "
                          f"link={x[f'{res}.status']:8} asset {x['asset.id']}  "
                          f"{x.get('campaign.name','(account)')} / {x.get('ad_group.name','-')}")
                    print(f"      {v}")
asyncio.run(m())
