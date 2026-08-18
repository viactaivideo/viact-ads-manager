"""Full inventory of every ad asset on active Search and PMax campaigns."""
import asyncio, json
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config

CID="3767588103"
OUT="/tmp/claude-0/-home-user-viact-ads-manager/26274bcb-f27c-5cac-bbc0-c9360bacb908/scratchpad/all_assets.json"

async def main():
    c=GoogleAdsClient(load_config())
    data={}

    data["campaigns"]=await c.search(
      "SELECT campaign.id, campaign.name, campaign.status, "
      "campaign.advertising_channel_type FROM campaign "
      "WHERE campaign.status='ENABLED'")

    data["rsa"]=await c.search(
      "SELECT campaign.name, ad_group.name, ad_group_ad.ad.id, "
      "ad_group_ad.ad.responsive_search_ad.headlines, "
      "ad_group_ad.ad.responsive_search_ad.descriptions, "
      "ad_group_ad.ad.final_urls "
      "FROM ad_group_ad WHERE campaign.status='ENABLED' "
      "AND ad_group.status='ENABLED' AND ad_group_ad.status='ENABLED' "
      "AND campaign.advertising_channel_type='SEARCH'")

    data["ag_assets"]=await c.search(
      "SELECT campaign.name, asset_group.id, asset_group.name, "
      "asset_group_asset.field_type, asset_group_asset.asset, "
      "asset.id, asset.text_asset.text, asset.type "
      "FROM asset_group_asset WHERE campaign.status='ENABLED' "
      "AND asset_group.status='ENABLED' AND asset_group_asset.status='ENABLED'")

    # account/campaign/adgroup level extension assets
    for lvl,res in (("customer","customer_asset"),
                    ("campaign","campaign_asset"),
                    ("ad_group","ad_group_asset")):
        flds=["asset.id","asset.type","asset.name",
              "asset.sitelink_asset.link_text","asset.sitelink_asset.description1",
              "asset.sitelink_asset.description2","asset.callout_asset.callout_text",
              "asset.structured_snippet_asset.header",
              "asset.structured_snippet_asset.values",
              "asset.promotion_asset.promotion_target",
              "asset.call_asset.phone_number",
              "asset.final_urls", f"{res}.field_type", f"{res}.status"]
        if lvl!="customer":
            flds.append("campaign.name"); flds.append("campaign.status")
        if lvl=="ad_group":
            flds.append("ad_group.name"); flds.append("ad_group.status")
        q=f"SELECT {', '.join(flds)} FROM {res}"
        if lvl!="customer":
            q+=" WHERE campaign.status='ENABLED'"
        if lvl=="ad_group":
            q+=" AND ad_group.status='ENABLED'"
        try:
            data[res]=await c.search(q)
        except Exception as e:
            data[res]={"error":str(e)[:400]}

    json.dump(data, open(OUT,"w"), indent=1, default=str)
    for k,v in data.items():
        print(k, len(v) if isinstance(v,list) else v)

asyncio.run(main())
