# -*- coding: utf-8 -*-
import asyncio, re, collections
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config
FAIL=[]
def chk(ok,msg):
    print(("  OK  " if ok else "  FAIL")+" "+msg)
    if not ok: FAIL.append(msg)
BAN=re.compile(r"\bdwss\b|works supervision|\d+\s?%|\b\d+x\b|\b\d+ hours?\b|\bno\.?\s?1\b|"
               r"\bbest\b|\bleading\b|\btop\b|\bguarantee\b|\bmost \w+|\bawarded\b",re.I)
HOLD={"CITF Listed Tech","CITF Listed Safety Tech","8 PTW Types in 1 App",
      "Trusted in 25+ Countries","50+ Singapore Projects","7+ Years Experience",
      "Trusted by A1 Contractors","Trusted by Large Builders","Trusted by SG Fleets",
      "Trusted by 100+ SG Contractors","MOM Vision Zero Ready","24/7 Site Monitoring",
      "Free Platform & 2 AI Modules","14Days Freemium +2 AI module",
      "Try Our 2 AI Modules & Get Hands on"}
async def m():
    c=GoogleAdsClient(load_config()); hits=[]
    ads=await c.search("SELECT campaign.name, campaign.status, ad_group.name, ad_group.status, "
      "ad_group_ad.status, ad_group_ad.ad.id, ad_group_ad.ad.responsive_search_ad.headlines, "
      "ad_group_ad.ad.responsive_search_ad.descriptions, ad_group_ad.ad.final_urls, "
      "ad_group_ad.ad_strength FROM ad_group_ad WHERE campaign.status='ENABLED' "
      "AND ad_group.status='ENABLED' AND ad_group_ad.status='ENABLED'")
    print("=== LIVE SEARCH ADS ===")
    for a in ads:
        # non-RSA formats (call-only, image) carry no headline list
        if "ad_group_ad.ad.responsive_search_ad.headlines" not in a: continue
        hs=[h["text"] for h in a["ad_group_ad.ad.responsive_search_ad.headlines"]]
        ds=[d["text"] for d in a.get("ad_group_ad.ad.responsive_search_ad.descriptions") or []]
        miss=[x for x in ("500+ Projects Worldwide","200+ Safety Modules") if x not in hs]
        dup=[t for t in set(hs) if hs.count(t)>1]
        chk(not miss and not dup, f"{a['campaign.name']:17} ad {a['ad_group_ad.ad.id']} "
            f"({len(hs)}H/{len(ds)}D) strength={a.get('ad_group_ad.ad_strength')}"
            + (f"  missing={miss} dup={dup}" if (miss or dup) else ""))
        for t in hs+ds:
            if t not in HOLD and BAN.search(t) and "500+" not in t and "200+" not in t:
                hits.append((a["campaign.name"],"ad text",t))
    print("\n=== SITELINK TRACKING TAGS ON ACTIVE CAMPAIGNS ===")
    dirty=0; tot=0
    for res in ("ad_group_asset","campaign_asset"):
        ag="ad_group.name, ad_group.status, " if res=="ad_group_asset" else ""
        q=(f"SELECT campaign.name, campaign.status, {ag}asset.id, asset.final_urls, "
           f"asset.sitelink_asset.link_text, {res}.status, {res}.field_type FROM {res} "
           f"WHERE {res}.status='ENABLED' AND {res}.field_type='SITELINK' "
           f"AND campaign.status='ENABLED'")
        if res=="ad_group_asset": q+=" AND ad_group.status='ENABLED'"
        for x in await c.search(q):
            tot+=1
            if "?" in (x.get("asset.final_urls") or [""])[0]:
                dirty+=1
                print(f"       still tagged: {x['campaign.name']} "
                      f"[{x.get('asset.sitelink_asset.link_text')}]")
    chk(dirty==0, f"{tot} live sitelinks, {dirty} still carrying a hardcoded tracking tag")
    print("\n=== CALLOUTS DUPLICATING A MANDATORY HEADLINE ===")
    d=0
    for res in ("customer_asset","campaign_asset","ad_group_asset"):
        camp="campaign.name, campaign.status, " if res!="customer_asset" else ""
        ag="ad_group.name, ad_group.status, " if res=="ad_group_asset" else ""
        q=(f"SELECT {camp}{ag}asset.callout_asset.callout_text, {res}.status FROM {res} "
           f"WHERE {res}.status='ENABLED' AND asset.type='CALLOUT'")
        if res!="customer_asset": q+=" AND campaign.status='ENABLED'"
        if res=="ad_group_asset": q+=" AND ad_group.status='ENABLED'"
        for x in await c.search(q):
            if x.get("asset.callout_asset.callout_text") in ("500+ Projects Worldwide","200+ Safety Modules"):
                d+=1; print(f"       {x.get('campaign.name','account')} "
                            f"{x['asset.callout_asset.callout_text']}")
    chk(d==0, f"{d} callouts still repeat a mandatory headline")
    print("\n=== UNPROVEN CLAIMS ANYWHERE ON ACTIVE CAMPAIGNS ===")
    for res in ("customer_asset","campaign_asset","ad_group_asset"):
        camp="campaign.name, campaign.status, " if res!="customer_asset" else ""
        ag="ad_group.name, ad_group.status, " if res=="ad_group_asset" else ""
        q=(f"SELECT {camp}{ag}asset.callout_asset.callout_text, asset.sitelink_asset.link_text, "
           f"asset.sitelink_asset.description1, asset.sitelink_asset.description2, "
           f"asset.structured_snippet_asset.values, {res}.status FROM {res} "
           f"WHERE {res}.status='ENABLED'")
        if res!="customer_asset": q+=" AND campaign.status='ENABLED'"
        if res=="ad_group_asset": q+=" AND ad_group.status='ENABLED'"
        for x in await c.search(q):
            for v in ([x.get("asset.callout_asset.callout_text"),
                       x.get("asset.sitelink_asset.link_text"),
                       x.get("asset.sitelink_asset.description1"),
                       x.get("asset.sitelink_asset.description2")]
                      + (x.get("asset.structured_snippet_asset.values") or [])):
                if v and v not in HOLD and BAN.search(v):
                    hits.append((x.get("campaign.name","account"),"extension",v))
    for x in await c.search("SELECT campaign.name, campaign.status, asset_group.name, "
      "asset_group.status, asset.text_asset.text, asset_group_asset.status "
      "FROM asset_group_asset WHERE campaign.status='ENABLED' AND asset_group.status='ENABLED' "
      "AND asset_group_asset.status='ENABLED'"):
        t=x.get("asset.text_asset.text")
        if t and t not in HOLD and BAN.search(t) and "500+" not in t and "200+" not in t:
            hits.append((x["campaign.name"],"pmax text",t))
    chk(not hits, f"{len(hits)} unproven claims outside the on-hold list")
    for h in hits: print("       ",h)
    print("\n"+"="*66)
    print(f"{len(FAIL)} FAILURES" if FAIL else "ALL CHECKS PASSED")
asyncio.run(m())
