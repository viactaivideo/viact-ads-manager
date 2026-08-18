# -*- coding: utf-8 -*-
"""Clean assets that only became live when the Permit To Work ad group was revived.

Yesterday's account-wide claim cleanup scoped enabled ad groups only, so these
sat dormant on a paused group and were never in scope. Reviving the group put
them into serving. Two categories, both already settled policy:
  - DWSS content: the owner does not support the product
  - unsubstantiated statistics: forbidden by docs/BRAND_CLAIMS.md
"""
import asyncio, sys, re
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config
CID="3767588103"; CAMP="22972642686"; APPLY="--apply" in sys.argv
R=lambda s,*i: f"customers/{CID}/{s}/" + "~".join(str(x) for x in i)
DWSS=re.compile(r"\bdwss\b|works supervision|digital supervision",re.I)
STAT=re.compile(r"\d+\s?%|\b\d+x\b",re.I)
async def m():
    c=GoogleAdsClient(load_config())
    ops={"ad_group_asset":[],"campaign_asset":[]}; plan=[]
    for res,owner in (("ad_group_asset","ad_group"),("campaign_asset","campaign")):
        extra=", ad_group.id, ad_group.status" if owner=="ad_group" else ""
        for x in await c.search(f"SELECT campaign.id{extra}, asset.id, asset.type, "
          "asset.callout_asset.callout_text, asset.sitelink_asset.link_text, "
          "asset.sitelink_asset.description1, asset.sitelink_asset.description2, "
          f"{res}.field_type, {res}.status FROM {res} WHERE campaign.id={CAMP} "
          f"AND {res}.status='ENABLED'"
          + (" AND ad_group.status='ENABLED'" if owner=="ad_group" else "")):
            vals=[x.get("asset.callout_asset.callout_text"),
                  x.get("asset.sitelink_asset.link_text"),
                  x.get("asset.sitelink_asset.description1"),
                  x.get("asset.sitelink_asset.description2")]
            joined=" ".join(v for v in vals if v)
            why=None
            if DWSS.search(joined): why="DWSS - product not supported"
            elif STAT.search(joined): why="unsubstantiated statistic"
            if not why: continue
            ft=x[f"{res}.field_type"]
            ids=(x["ad_group.id"],x["asset.id"],ft) if owner=="ad_group" else (CAMP,x["asset.id"],ft)
            key="adGroupAssets" if owner=="ad_group" else "campaignAssets"
            ops[res].append({"remove":R(key,*ids)})
            plan.append((owner,ft,x["asset.id"],joined[:70],why))
    print(f"{len(plan)} assets to detach\n")
    for p in plan: print(f"  {p[0]:9} {p[1]:19} {p[2]:>13}  [{p[4]}]\n      {p[3]}")
    V=not APPLY
    for res,o in ops.items():
        if not o: continue
        r=await c.mutate(res,o,validate_only=V)
        print(f"\n{res}: {'APPLIED' if APPLY else 'VALIDATED'} {len(r.get('results',[]))} of {len(o)}")
asyncio.run(m())
