# -*- coding: utf-8 -*-
"""Pending items, part 1: duplicate callouts, redundant suffixes, dormant stats."""
import asyncio, sys, re
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config
CID="3767588103"; APPLY="--apply" in sys.argv
R=lambda s,*i: f"customers/{CID}/{s}/" + "~".join(str(x) for x in i)
CLAIMS=("500+ Projects Worldwide","200+ Safety Modules")
ACCOUNT_ADD=["Works With Existing CCTV","Multi-Site Deployment"]
STAT=re.compile(r"\d+\s?%|\b\d+x\b|\b\d+ hours?\b",re.I)
log=[]
async def m():
    c=GoogleAdsClient(load_config()); V=not APPLY

    # ---- A. callouts that duplicate a mandatory headline -------------
    print("=== A. CALLOUTS DUPLICATING A MANDATORY HEADLINE ===")
    ops={"customer_asset":[],"campaign_asset":[],"ad_group_asset":[]}
    for res in ops:
        camp="campaign.name, campaign.status, campaign.id, " if res!="customer_asset" else ""
        ag="ad_group.name, ad_group.status, ad_group.id, " if res=="ad_group_asset" else ""
        q=(f"SELECT {camp}{ag}asset.id, asset.callout_asset.callout_text, {res}.status "
           f"FROM {res} WHERE {res}.status='ENABLED' AND asset.type='CALLOUT'")
        if res!="customer_asset": q+=" AND campaign.status='ENABLED'"
        if res=="ad_group_asset": q+=" AND ad_group.status='ENABLED'"
        for x in await c.search(q):
            t=x.get("asset.callout_asset.callout_text")
            if t not in CLAIMS: continue
            key={"customer_asset":"customerAssets","campaign_asset":"campaignAssets",
                 "ad_group_asset":"adGroupAssets"}[res]
            ids=(x["asset.id"],"CALLOUT") if res=="customer_asset" else (
                 (x["ad_group.id"] if res=="ad_group_asset" else x["campaign.id"]),
                 x["asset.id"],"CALLOUT")
            ops[res].append({"remove":R(key,*ids)})
            where=("Account level" if res=="customer_asset" else
                   (f"{x['campaign.name']} (campaign)" if res=="campaign_asset"
                    else f"{x['campaign.name']} / {x['ad_group.name']}"))
            log.append(("Callouts",t,"(removed - already a headline in every ad here)",where))
            print(f"  remove  {t:26} {where}")
    have={x["asset.callout_asset.callout_text"]:str(x["asset.id"]) for x in await c.search(
        "SELECT asset.id, asset.callout_asset.callout_text FROM asset WHERE asset.type='CALLOUT' "
        "AND asset.callout_asset.callout_text IN (" + ",".join(f"'{t}'" for t in ACCOUNT_ADD) + ")")}
    miss=[t for t in ACCOUNT_ADD if t not in have]
    if miss:
        rr=await c.mutate("asset",[{"create":{"name":t,"calloutAsset":{"calloutText":t}}}
                                   for t in miss],validate_only=V)
        for t,x in zip(miss,rr.get("results",[])):
            have[t]=x.get("resourceName","").rsplit("/",1)[-1] or None
    for t in ACCOUNT_ADD:
        if have.get(t):
            ops["customer_asset"].append({"create":{"asset":R("assets",have[t]),"fieldType":"CALLOUT"}})
        log.append(("Callouts","(none - new asset)",t,"Account level - replaces the two removed"))
        print(f"  add     {t:26} Account level")
    for res,o in ops.items():
        if o:
            r=await c.mutate(res,o,validate_only=V)
            print(f"    {res}: {'APPLIED' if APPLY else 'VALIDATED'} {len(r.get('results',[]))} of {len(o)}")

    # ---- B. redundant ad-group final URL suffixes --------------------
    print("\n=== B. REDUNDANT AD-GROUP URL SUFFIXES ===")
    camp={x["campaign.id"]:(x["campaign.name"],x.get("campaign.final_url_suffix"))
          for x in await c.search("SELECT campaign.id, campaign.name, campaign.status, "
            "campaign.final_url_suffix FROM campaign WHERE campaign.status='ENABLED'")}
    ops=[]
    for x in await c.search("SELECT campaign.id, campaign.name, campaign.status, ad_group.id, "
      "ad_group.name, ad_group.status, ad_group.final_url_suffix FROM ad_group "
      "WHERE campaign.status='ENABLED' AND ad_group.status='ENABLED'"):
        s=x.get("ad_group.final_url_suffix"); cs=camp.get(x["campaign.id"],("",None))[1]
        if s is None or s!=cs: continue
        ops.append({"update":{"resourceName":R("adGroups",x["ad_group.id"]),"finalUrlSuffix":""},
                    "updateMask":"final_url_suffix"})
        log.append(("Keywords","Ad group carries its own copy of the campaign tracking tag",
                    "Inherits from the campaign - one place to update instead of sixteen",
                    f"{x['campaign.name']} / {x['ad_group.name']}"))
        print(f"  clear   {x['campaign.name']} / {x['ad_group.name']}")
    if ops:
        r=await c.mutate("ad_group",ops,validate_only=V)
        print(f"    {'APPLIED' if APPLY else 'VALIDATED'} {len(r.get('results',[]))} of {len(ops)}")

    # ---- C. statistic callouts on dormant ad groups -------------------
    print("\n=== C. STATISTIC CALLOUTS ON DORMANT AD GROUPS ===")
    ops=[]
    for x in await c.search("SELECT campaign.name, campaign.status, ad_group.name, ad_group.id, "
      "ad_group.status, asset.id, asset.callout_asset.callout_text, ad_group_asset.status "
      "FROM ad_group_asset WHERE ad_group_asset.status='ENABLED' AND asset.type='CALLOUT'"):
        t=x.get("asset.callout_asset.callout_text") or ""
        if not STAT.search(t): continue
        ops.append({"remove":R("adGroupAssets",x["ad_group.id"],x["asset.id"],"CALLOUT")})
        log.append(("Callouts",t,"(removed - unproven figure)",
                    f"{x['campaign.name']} / {x['ad_group.name']} (dormant)"))
        print(f"  remove  {t:28} {x['campaign.name']} / {x['ad_group.name']} "
              f"(camp={x['campaign.status']}, group={x['ad_group.status']})")
    for x in await c.search("SELECT campaign.name, campaign.status, campaign.id, asset.id, "
      "asset.callout_asset.callout_text, campaign_asset.status FROM campaign_asset "
      "WHERE campaign_asset.status='ENABLED' AND asset.type='CALLOUT'"):
        t=x.get("asset.callout_asset.callout_text") or ""
        if not STAT.search(t): continue
        ops.append({"remove":R("campaignAssets",x["campaign.id"],x["asset.id"],"CALLOUT")})
        log.append(("Callouts",t,"(removed - unproven figure)",f"{x['campaign.name']} (campaign)"))
        print(f"  remove  {t:28} {x['campaign.name']} (campaign level, {x['campaign.status']})")
    if ops:
        agops=[o for o in ops if "adGroupAssets" in o["remove"]]
        cops=[o for o in ops if "campaignAssets" in o["remove"]]
        for res,oo in (("ad_group_asset",agops),("campaign_asset",cops)):
            if oo:
                r=await c.mutate(res,oo,validate_only=V)
                print(f"    {res}: {'APPLIED' if APPLY else 'VALIDATED'} {len(r.get('results',[]))} of {len(oo)}")
    import json
    json.dump(log,open("/tmp/claude-0/-home-user-viact-ads-manager/26274bcb-f27c-5cac-bbc0-c9360bacb908/scratchpad/pending1_log.json","w"),indent=1)
    print(f"\n{len(log)} changes")
asyncio.run(m())
