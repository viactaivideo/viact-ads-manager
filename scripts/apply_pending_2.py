# -*- coding: utf-8 -*-
"""Pending part 2: enterprise RSA, ePTW snippet, sitelink tracking tags.

No CITF wording and no DWSS anywhere - both were ruled out by the owner.
"""
import asyncio, sys, re, json
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config
CID="3767588103"; APPLY="--apply" in sys.argv
AG_4S="189327327009"; AG_PTW="195039132719"
R=lambda s,*i: f"customers/{CID}/{s}/" + "~".join(str(x) for x in i)
log=[]
H=["500+ Projects Worldwide","200+ Safety Modules","{KeyWord:Smart Site Safety System}",
   "4S For Main Contractors","Enterprise 4S Deployment","Multi-Site Safety Control",
   "ePTW, PPE & Crane In One","Built For HK Construction","Works With Existing CCTV",
   "Centralised Site Control","One Platform, Every Site","Book An Enterprise Demo",
   "Confined Space Monitoring","AI Site Safety Monitoring","Smart Site Safety Platform"]
D=["4S Platform Built For Hong Kong Main Contractors And Multi-Site Operations.",
   "Run ePTW, PPE Detection, Crane And Confined Space Safety From One Central Platform.",
   "Deploy Across Multiple Sites Using Your Existing CCTV And IP Cameras.",
   "Book A Technical Demo With Our Hong Kong Team. 500+ Projects Worldwide."]
SNIP=("Service catalog",["Hot Work Permits","Cold Work Permits","Confined Space Entry",
                        "Electrical Work","Excavation Work"])
KI=re.compile(r"^\{keyword:(.*)\}$",re.I|re.S)
def eff(t):
    m=KI.match(t.strip()); return len(m.group(1)) if m else len(t)
BAN=re.compile(r"\bcitf\b|\bdwss\b|works supervision|\d+\s?%|\b\d+x\b|\bno\.?\s?1\b|\bbest\b|"
               r"\bleading\b|\btop\b|\bguarantee\b|100\s?%|\bmost \w+|\bawarded\b",re.I)
def validate():
    bad=[]
    for t in H:
        if eff(t)>30: bad.append(f"headline {t!r} {eff(t)}")
        if BAN.search(t) and t not in ("500+ Projects Worldwide","200+ Safety Modules"):
            bad.append(f"BANNED wording in {t!r}")
    if len(set(H))!=len(H): bad.append("duplicate headline")
    for t in D:
        if len(t)>90: bad.append(f"description {t!r} {len(t)}")
        if BAN.search(t) and "500+ Projects Worldwide" not in t: bad.append(f"BANNED wording in {t!r}")
    for v in SNIP[1]:
        if len(v)>25: bad.append(f"snippet value {v!r}")
    if len(SNIP[1])<3: bad.append("snippet needs 3+ values")
    for x in ("500+ Projects Worldwide","200+ Safety Modules"):
        if x not in H: bad.append(f"missing mandatory {x}")
    return bad
async def m():
    bad=validate()
    if bad: print("VALIDATION FAILED:"); [print("  ",b) for b in bad]; return
    print("Validation passed: no CITF, no DWSS, no statistic, no ranking claim, "
          "both mandatory headlines present, all within limits.\n")
    c=GoogleAdsClient(load_config()); V=not APPLY

    # ---- D. third RSA on the HK 4S ad group -------------------------
    ad={"responsiveSearchAd":{"headlines":[{"text":t} for t in H],
                              "descriptions":[{"text":t} for t in D],
                              "path1":"smart_site","path2":"safety_system"},
        "finalUrls":["https://www.viact.ai/smart-site-safety-system"]}
    r=await c.mutate("ad_group_ad",[{"create":{"adGroup":R("adGroups",AG_4S),
        "status":"ENABLED","ad":ad}}],validate_only=V)
    print(f"[D] enterprise RSA on HK Smart Site Safety System: {len(r.get('results',[]))}")
    for t in H: log.append(("Headlines","(none - new ad)",t,"HK_Search_Leads / Smart Site Safety System"))
    for t in D: log.append(("Descriptions","(none - new ad)",t,"HK_Search_Leads / Smart Site Safety System"))

    # ---- E. structured snippet on the ePTW ad group ------------------
    rr=await c.mutate("asset",[{"create":{"name":f"Snippet - {SNIP[0]} - PTW",
        "structuredSnippetAsset":{"header":SNIP[0],"values":SNIP[1]}}}],validate_only=V)
    sid=(rr.get("results") or [{}])[0].get("resourceName","").rsplit("/",1)[-1]
    if sid:
        r=await c.mutate("ad_group_asset",[{"create":{"adGroup":R("adGroups",AG_PTW),
            "asset":R("assets",sid),"fieldType":"STRUCTURED_SNIPPET"}}],validate_only=V)
        print(f"[E] ePTW structured snippet: {len(r.get('results',[]))}")
    log.append(("Structured Snippets","(none - ad group had no snippet)",
                f"{SNIP[0]}: {', '.join(SNIP[1])}","HK_Search_Leads / Permit To Work"))

    # ---- F. sitelinks carrying hardcoded tracking tags ---------------
    rows=await c.search("SELECT campaign.name, campaign.status, campaign.id, ad_group.name, "
      "ad_group.id, ad_group.status, asset.id, asset.sitelink_asset.link_text, "
      "asset.sitelink_asset.description1, asset.sitelink_asset.description2, asset.final_urls, "
      "ad_group_asset.status FROM ad_group_asset WHERE ad_group_asset.status='ENABLED' "
      "AND ad_group_asset.field_type='SITELINK' AND campaign.status='ENABLED' "
      "AND ad_group.status='ENABLED'")
    rows+=await c.search("SELECT campaign.name, campaign.status, campaign.id, asset.id, "
      "asset.sitelink_asset.link_text, asset.sitelink_asset.description1, "
      "asset.sitelink_asset.description2, asset.final_urls, campaign_asset.status "
      "FROM campaign_asset WHERE campaign_asset.status='ENABLED' "
      "AND campaign_asset.field_type='SITELINK' AND campaign.status='ENABLED'")
    dirty=[]
    for x in rows:
        u=(x.get("asset.final_urls") or [""])[0]
        if "?" in u and x.get("asset.sitelink_asset.description1"): dirty.append(x)
    print(f"[F] sitelinks with hardcoded tracking tags on active campaigns: {len(dirty)}")
    uniq={}
    for x in dirty:
        k=(x["asset.id"])
        uniq.setdefault(k,{"row":x,"places":[]})
        uniq[k]["places"].append(x)
    print(f"    distinct assets to rebuild: {len(uniq)}")
    creates=[]
    for aid,v in uniq.items():
        x=v["row"]
        creates.append({"create":{"name":x["asset.sitelink_asset.link_text"],
            "finalUrls":[(x["asset.final_urls"] or [""])[0].split("?")[0]],
            "sitelinkAsset":{"linkText":x["asset.sitelink_asset.link_text"],
                "description1":x["asset.sitelink_asset.description1"],
                "description2":x.get("asset.sitelink_asset.description2") or ""}}})
    newid={}
    if creates:
        rr=await c.mutate("asset",creates,validate_only=V)
        for aid,res in zip(uniq,rr.get("results",[])):
            newid[aid]=res.get("resourceName","").rsplit("/",1)[-1] or None
    agops=[]; cops=[]
    for aid,v in uniq.items():
        n=newid.get(aid)
        for x in v["places"]:
            is_ag="ad_group.id" in x
            old=(x["asset.final_urls"] or [""])[0]
            where=(f"{x['campaign.name']} / {x['ad_group.name']}" if is_ag
                   else f"{x['campaign.name']} (campaign)")
            log.append(("Sitelinks",
                f"{x['asset.sitelink_asset.link_text']} | {old[:70]}",
                f"{x['asset.sitelink_asset.link_text']} | {old.split('?')[0]}",where))
            if is_ag:
                if n: agops.append({"create":{"adGroup":R("adGroups",x["ad_group.id"]),
                        "asset":R("assets",n),"fieldType":"SITELINK"}})
                agops.append({"remove":R("adGroupAssets",x["ad_group.id"],aid,"SITELINK")})
            else:
                if n: cops.append({"create":{"campaign":R("campaigns",x["campaign.id"]),
                        "asset":R("assets",n),"fieldType":"SITELINK"}})
                cops.append({"remove":R("campaignAssets",x["campaign.id"],aid,"SITELINK")})
    for res,o in (("ad_group_asset",agops),("campaign_asset",cops)):
        if o:
            r=await c.mutate(res,o,validate_only=V)
            print(f"    {res}: {'APPLIED' if APPLY else 'VALIDATED'} {len(r.get('results',[]))} of {len(o)}")
    json.dump(log,open("/tmp/claude-0/-home-user-viact-ads-manager/26274bcb-f27c-5cac-bbc0-c9360bacb908/scratchpad/pending2_log.json","w"),indent=1)
    print(f"\n{len(log)} changes logged")
asyncio.run(m())
