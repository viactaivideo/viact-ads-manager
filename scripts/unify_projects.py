# -*- coding: utf-8 -*-
"""Same treatment for the projects claim: 300+ Successful Projects -> canon.

The Singapore-specific counts ("30+ Projects with Housing and Development
Board and 50+ A1 Contractors") are NOT touched. They name a specific client
and a regional figure, so they are a different claim with no approved wording
- guessing a number there would be worse than reporting it.
"""
import asyncio, sys
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config
CID="3767588103"; APPLY="--apply" in sys.argv
R=lambda s,*i: f"customers/{CID}/{s}/" + "~".join(str(x) for x in i)
CANON="500+ Projects Worldwide"
VARIANTS={"300+ Successful Projects","300+ Projects","500+ Global Projects",
          "400+ Successful Projects","300+ Projects Worldwide"}
async def m():
    assert len(CANON)<=30
    c=GoogleAdsClient(load_config()); V=not APPLY; plan=[]; skip=[]
    ads=await c.search("SELECT campaign.name, campaign.status, ad_group.name, ad_group.status, "
      "ad_group_ad.status, ad_group_ad.ad.id, ad_group_ad.ad.responsive_search_ad.headlines, "
      "ad_group_ad.ad.responsive_search_ad.descriptions FROM ad_group_ad "
      "WHERE ad_group_ad.status!='REMOVED'")
    ops=[]
    for a in ads:
        aid=str(a["ad_group_ad.ad.id"])
        hs=[dict(h) for h in a.get("ad_group_ad.ad.responsive_search_ad.headlines") or []]
        if not hs: continue
        touched=False
        for h in hs:
            if h.get("text") in VARIANTS:
                if any(o.get("text")==CANON for o in hs if o is not h):
                    skip.append((aid,a["campaign.name"],h["text"],
                                 "ad already carries the approved wording"))
                    continue
                plan.append((f"{a['campaign.name']} / {a['ad_group.name']}",aid,h["text"],
                             a["campaign.status"],a["ad_group.status"],a["ad_group_ad.status"]))
                h["text"]=CANON; touched=True
        if not touched: continue
        txt=[h["text"] for h in hs]
        dup=[t for t in set(txt) if txt.count(t)>1]
        if dup: print(f"  !! ad {aid} would duplicate {dup} - aborting"); return
        ops.append({"update":{"resourceName":R("ads",aid),
            "responsiveSearchAd":{"headlines":hs}},
            "updateMask":"responsive_search_ad.headlines"})
    print(f"search ads to update: {len(ops)}")
    if ops:
        r=await c.mutate("ad",ops,validate_only=V)
        print(f"  {'APPLIED' if APPLY else 'VALIDATED'} {len(r.get('results',[]))}")
    pm=await c.search("SELECT campaign.name, campaign.status, asset_group.id, asset_group.name, "
      "asset_group.status, asset_group_asset.field_type, asset_group_asset.status, asset.id, "
      "asset.text_asset.text FROM asset_group_asset WHERE asset_group_asset.status='ENABLED' "
      "AND asset_group_asset.field_type='HEADLINE'")
    have={x["asset_group.id"] for x in pm if x.get("asset.text_asset.text")==CANON}
    pops=[]
    for x in pm:
        if x.get("asset.text_asset.text") not in VARIANTS: continue
        gid=x["asset_group.id"]
        pops.append({"remove":R("assetGroupAssets",gid,x["asset.id"],"HEADLINE")})
        plan.append((f"{x['campaign.name']} / {x['asset_group.name']} (PMax)",x["asset.id"],
                     x["asset.text_asset.text"],x["campaign.status"],x["asset_group.status"],
                     x["asset_group_asset.status"]))
        if gid not in have:
            pops.append({"create":{"assetGroup":R("assetGroups",gid),
                "asset":R("assets","335645647265"),"fieldType":"HEADLINE"}}); have.add(gid)
        else: skip.append((gid,x["campaign.name"],x["asset.text_asset.text"],
                           "asset group already carries the approved wording"))
    print(f"PMax link operations: {len(pops)}")
    if pops:
        r=await c.mutate("asset_group_asset",pops,validate_only=V)
        print(f"  {'APPLIED' if APPLY else 'VALIDATED'} {len(r.get('results',[]))}")
    print(f"\n=== {len(plan)} REPLACED with '{CANON}' ===")
    for loc,i,old,cs,gs,as_ in plan:
        live="LIVE" if cs==gs==as_=="ENABLED" else "not serving"
        print(f"  [{live:11}] {loc}  ({i})  was: {old}")
    if skip:
        print(f"\n=== {len(skip)} skipped ===")
        for s in skip: print(f"  {s[1]} ({s[0]}): {s[2]!r} - {s[3]}")
asyncio.run(m())
