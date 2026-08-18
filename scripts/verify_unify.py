# -*- coding: utf-8 -*-
"""Post-change sweep: any module OR project count variant left anywhere."""
import asyncio, re
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config
MOD=re.compile(r"\b\d+\s*\+?\s*(?:ai|smart|safety|pre-?built|in-?built)?\s*(?:ai|smart|safety)?\s*"
               r"(?:modules?|rules?|models?)\b|模組", re.I)
PROJ=re.compile(r"\b\d+\s*\+?\s*(?:successful|global|worldwide|live)?\s*projects?\b", re.I)
CM="200+ Safety Modules"; CP="500+ Projects Worldwide"
async def m():
    c=GoogleAdsClient(load_config())
    bad=[]
    def look(loc,kind,ident,text,cs,gs,as_):
        if not text: return
        mm=MOD.search(text); pp=PROJ.search(text)
        if not (mm or pp): return
        okm = (not mm) or (CM in text)
        okp = (not pp) or (CP in text)
        if okm and okp: return
        live = cs=="ENABLED" and gs=="ENABLED" and as_=="ENABLED"
        bad.append((live,loc,kind,str(ident),text))
    for a in await c.search("SELECT campaign.name, campaign.status, ad_group.name, ad_group.status, "
      "ad_group_ad.status, ad_group_ad.ad.id, ad_group_ad.ad.responsive_search_ad.headlines, "
      "ad_group_ad.ad.responsive_search_ad.descriptions FROM ad_group_ad "
      "WHERE ad_group_ad.status!='REMOVED'"):
        for f,lab in (("headlines","headline"),("descriptions","description")):
            for i in a.get(f"ad_group_ad.ad.responsive_search_ad.{f}") or []:
                look(f"{a['campaign.name']} / {a['ad_group.name']}",lab,a["ad_group_ad.ad.id"],
                     i["text"],a["campaign.status"],a["ad_group.status"],a["ad_group_ad.status"])
    for x in await c.search("SELECT campaign.name, campaign.status, asset_group.name, asset_group.status, "
      "asset_group_asset.field_type, asset_group_asset.status, asset.id, asset.text_asset.text "
      "FROM asset_group_asset WHERE asset_group_asset.status!='REMOVED'"):
        look(f"{x['campaign.name']} / {x['asset_group.name']}",
             f"PMax {x['asset_group_asset.field_type'].lower()}",x["asset.id"],
             x.get("asset.text_asset.text"),x["campaign.status"],x["asset_group.status"],
             x["asset_group_asset.status"])
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
                look(f"{x.get('campaign.name','ACCOUNT')} / {x.get('ad_group.name','-')}",
                     f"{res.replace('_asset','')} {x[f'{res}.field_type'].lower()}",x["asset.id"],v,
                     x.get("campaign.status","ENABLED"),x.get("ad_group.status","ENABLED"),
                     x[f"{res}.status"])
    live=[b for b in bad if b[0]]; dorm=[b for b in bad if not b[0]]
    print(f"=== ON UNITS THAT ARE ACTUALLY SERVING: {len(live)} ===")
    for _,loc,k,i,t in live: print(f"  {k:22} {i:>14} {loc}\n      {t}")
    if not live: print("  none")
    print(f"\n=== ON PAUSED / DORMANT UNITS: {len(dorm)} ===")
    for _,loc,k,i,t in dorm: print(f"  {k:22} {i:>14} {loc}\n      {t}")
    if not dorm: print("  none")
asyncio.run(m())
