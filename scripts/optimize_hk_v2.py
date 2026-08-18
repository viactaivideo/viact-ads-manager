# -*- coding: utf-8 -*-
"""HK_Search_Leads optimisation.

Excluded by instruction: DWSS (viAct does not support the product) and every
CITF claim (listing could not be independently verified; owner asked to hold).
No new statistic, ranking, endorsement or customer count appears anywhere.
"""
import asyncio, sys, json
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config

CID="3767588103"; CAMP="22972642686"
AG_4S="189327327009"; AG_PTW="195039132719"
APPLY="--apply" in sys.argv
R=lambda s,*i: f"customers/{CID}/{s}/" + "~".join(str(x) for x in i)
M=lambda hk: int(round(hk*1_000_000))

# ---- 1. bids (HK$). Set BEFORE the strategy switch: every bid is HK$0.01
#         today and Manual CPC would stop the campaign serving instantly.
AG_BID={AG_4S:25.0, AG_PTW:20.0}
KW_BID={  # criterion_id -> HK$, tiered on demonstrated conversion history
 "934700525401":32.0,   # construction safety solution  8 conv, CPA HK$286
 "2280181861576":30.0,  # ai site safety monitoring     5 conv, CPA HK$508
 "2626124749912":30.0,  # smart site safety system hong kong  2 conv, CPA HK$213
 "2392662242768":26.0,  # site safety smart system      3 conv
 "379171177369":26.0,   # construction site safety software  3 conv
 "2283695289543":22.0,  # 4s safety system              2 conv
 "296321714147":22.0,   # construction site safety      1 conv
 "500022407003":22.0,   # site safety system            1 conv
 "1416113920315":22.0,  # ai construction safety        1 conv (broad variant)
}
# ---- 2. keyword state changes
ENABLE=[  # criterion_id, text, why
 ("934700525401","construction safety solution","8 conv on HK$2,290 - best CPA in the account"),
 ("2283695289543","4s safety system","2 conv on HK$4,909"),
 ("296321714147","construction site safety","1 conv on HK$2,768"),
 ("500022407003","site safety system","1 conv on HK$1,842"),
 ("1416113920315","ai construction safety","1 conv (broad variant); re-enabled as phrase"),
 ("2480766868008","smart site safety system provider","vendor-seeking, core category"),
 ("2480766867968","smart site safety system vendor","vendor-seeking, core category"),
 ("2463719215166","4s system providers hong kong","vendor-seeking, HK-qualified"),
 ("2480766867528","ssss vendor hong kong","vendor-seeking, HK-qualified"),
 ("2468002180457","4s system hong kong","category + market"),
 ("2391007685182","4s smart site safety system","41 clicks at HK$17.10 CPC, cheapest core term"),
]
PAUSE=[
 ("1935022359035","smart site safety system (BROAD)",
  "broad pulled in scheme-research and hardware queries; phrase covers the same demand"),
 # generic permit-type queries: form/template seekers, not software buyers
 ("PTW:hot work permit",None,None),
]
PAUSE_PTW_TEXTS={"hot work permit","Cold Work Permit","General Work Permit",
                 "Electrical Work Permit","Excavation Permit"}
NEW_KW=[  # ad_group, text, match, bid
 (AG_4S,"smart site safety system","PHRASE",28.0),   # was REMOVED: 6 conv on HK$8,438
 (AG_4S,"4s solution provider hong kong","PHRASE",18.0),
 (AG_4S,"4s platform main contractor","PHRASE",18.0),
 (AG_4S,"multi site safety monitoring system","PHRASE",18.0),
 (AG_4S,"construction safety platform enterprise","PHRASE",18.0),
]
# ---- 3. campaign negatives
NEG={
 "DWSS - product not supported":["dwss","digital works supervision","works supervision","risc form"],
 "4S scheme research, not vendor-seeking":["labelling scheme","labeling scheme","4sls",
   "technical circular","briefing session","webinar","4s application form"],
 "Contractor internal worker apps":["gammon","zero harm","zeroharm","induction centre","induction card"],
 "Physical safety equipment":["fall arrest","fall arrester","anti fall device","safety harness",
   "harness inspection","safety equipment","safety supplies","barricade","signage"],
 "CCTV and camera hardware brands":["hikvision","dahua","uniview","avigilon","ivms",
   "camera price","360 camera","cctv installation","ai box"],
 "Jobs, training and study":["job","jobs","vacancy","salary","recruitment","career","course",
   "training","certificate","diploma","exam","student","intern","resume"],
 "Documents and templates":["pdf","template","ppt","powerpoint","sample","example",
   "free download","slideshare","manual"],
 "Free / DIY / low budget":["free","cheap","cheapest","lowest price","diy","open source","freeware"],
 "Existing users and app-seekers":["login","sign in","portal","app download","safetyculture"],
 "Consumer / residential":["residential","apartment","domestic helper","home use"],
}
# ---- 4. ad copy repairs on the two revived PTW ads
PTW_H={
 "806291948568":{"Save 7 Hours Daily on PTW":"500+ Projects Worldwide",
                 "Cut Authorization Delays 80%":"200+ Safety Modules"},
 "812925592257":{"Speed Up Site Operations":"500+ Projects Worldwide",
                 "Digital Permits For Industry":"200+ Safety Modules"},
}
PTW_D={
 "806291948568":{"Replace Paper PTW With AI-Driven Digital Permits Across HK Sites. Days To Minutes":
                 "Replace Paper PTW With AI-Driven Digital Permits Across Hong Kong Sites."},
}
PTW_URL="https://www.viact.ai/permit-to-work-software"   # strip hardcoded UTMs

# ---- 5. new assets for the live 4S ad group
SITELINKS=[
 ("Book An Enterprise Demo","Live 4S Demo On Your Site","Talk To A 4S Specialist",
  "https://www.viact.ai/demo"),
 ("Talk To Our Sales Team","Discuss Scope And Rollout","Speak With A Specialist",
  "https://www.viact.ai/contactsales"),
 ("Centralised 4S Platform","One Dashboard, Every Site","Access Anytime, Anywhere",
  "https://www.viact.ai/vihub"),
 ("Confined Space Safety","AI Confined Space Monitoring","Monitor High-Risk Spaces",
  "https://www.viact.ai/confined-space-safety-monitoring"),
]
CALLOUTS=["Multi-Site Deployment","Works With Existing CCTV",
          "500+ Projects Worldwide","200+ Safety Modules"]
SNIPPET=("Service catalog",["PPE Detection","Permit-to-Work","Crane Safety",
                           "Confined Space Safety","Area Control","Proximity Detection"])

def validate():
    bad=[]
    for lt,d1,d2,u in SITELINKS:
        if len(lt)>25: bad.append(f"sitelink text {lt!r} {len(lt)}>25")
        for d in (d1,d2):
            if len(d)>35: bad.append(f"sitelink desc {d!r} {len(d)}>35")
        if not u.startswith("https://www.viact.ai/"): bad.append(f"url {u}")
        if "?" in u: bad.append(f"hardcoded UTM in {u}")
    for t in CALLOUTS:
        if len(t)>25: bad.append(f"callout {t!r} {len(t)}>25")
    h,vals=SNIPPET
    if len(h)>25: bad.append("snippet header")
    if len(vals)<3: bad.append("snippet needs 3+ values")
    for v in vals:
        if len(v)>25: bad.append(f"snippet value {v!r} {len(v)}>25")
    for m in (PTW_H,):
        for aid,rep in m.items():
            for o,n in rep.items():
                if len(n)>30: bad.append(f"headline {n!r} {len(n)}>30")
    for aid,rep in PTW_D.items():
        for o,n in rep.items():
            if len(n)>90: bad.append(f"description {n!r} {len(n)}>90")
    blob=" ".join([t for t in CALLOUTS]+[x for s in SITELINKS for x in s[:3]]
                  +[n for r in PTW_H.values() for n in r.values()]
                  +[n for r in PTW_D.values() for n in r.values()])
    import re
    for pat,label in ((r"\bcitf\b","CITF claim"),(r"\bdwss\b","DWSS mention"),
                      (r"\d+\s?%|\b\d+x\b","statistic"),(r"\bno\.?\s?1\b|\bbest\b|\bleading\b|\btop\b","superiority"),
                      (r"\bguarantee\b|100\s?%","absolute")):
        if re.search(pat,blob,re.I): bad.append(f"BLOCKED {label} in new copy")
    return bad


async def main():
    bad=validate()
    if bad:
        print("VALIDATION FAILED - nothing sent:"); [print("  ",b) for b in bad]; return
    print("Pre-flight validation passed: no CITF, no DWSS, no statistic, no superiority,"
          " no absolute claim, all within Google length limits.\n")
    c=GoogleAdsClient(load_config()); log=[]
    V=not APPLY

    # ---------- STAGE 1: bids first, then bidding strategy -------------
    # One op per ad group: the PTW group needs both a bid and a status change,
    # and Google rejects the same resource twice in a single mutate.
    ops=[]
    for ag,b in AG_BID.items():
        pay={"resourceName":R("adGroups",ag),"cpcBidMicros":M(b)}
        mask="cpc_bid_micros"
        if ag==AG_PTW:
            pay["status"]="ENABLED"; mask="cpc_bid_micros,status"
        ops.append({"update":pay,"updateMask":mask})
    r=await c.mutate("ad_group",ops,validate_only=V)
    print(f"[1a] ad group bids + revive Permit To Work: {len(ops)} ops -> {len(r.get('results',[]))}")
    for ag,b in AG_BID.items(): log.append(("bid","ad group",ag,f"default CPC HK${b:.2f}"))
    log.append(("status","ad group",AG_PTW,"PAUSED -> ENABLED"))

    kops=[{"update":{"resourceName":R("adGroupCriteria",AG_4S,k),"cpcBidMicros":M(b)},
           "updateMask":"cpc_bid_micros"} for k,b in KW_BID.items()]
    r=await c.mutate("ad_group_criterion",kops,validate_only=V)
    print(f"[1b] keyword bids: {len(kops)} ops -> {len(r.get('results',[]))}")

    # manual_cpc is a message field: Google rejects it in a mask unless a leaf
    # subfield is named, so the mask points at enhanced_cpc_enabled.
    r=await c.mutate("campaign",[{"update":{"resourceName":R("campaigns",CAMP),
        "manualCpc":{"enhancedCpcEnabled":False}},
        "updateMask":"manual_cpc.enhanced_cpc_enabled"}],validate_only=V)
    print(f"[1c] bidding strategy -> MANUAL_CPC -> {len(r.get('results',[]))}")
    log.append(("bidding","campaign",CAMP,"MAXIMIZE_CONVERSIONS -> MANUAL_CPC"))

    # ---------- STAGE 2: keyword states --------------------------------
    ops=[{"update":{"resourceName":R("adGroupCriteria",AG_4S,k),"status":"ENABLED"},
          "updateMask":"status"} for k,_,_ in ENABLE]
    ops.append({"update":{"resourceName":R("adGroupCriteria",AG_4S,"1935022359035"),
                "status":"PAUSED"},"updateMask":"status"})
    ptw=await c.search("SELECT ad_group.id, ad_group_criterion.criterion_id, "
      "ad_group_criterion.keyword.text, ad_group_criterion.status, ad_group_criterion.negative "
      f"FROM ad_group_criterion WHERE ad_group.id={AG_PTW} AND ad_group_criterion.type='KEYWORD' "
      "AND ad_group_criterion.status='ENABLED'")
    npause=0
    for x in ptw:
        if x.get("ad_group_criterion.negative"): continue
        if x["ad_group_criterion.keyword.text"] in PAUSE_PTW_TEXTS:
            ops.append({"update":{"resourceName":R("adGroupCriteria",AG_PTW,
                x["ad_group_criterion.criterion_id"]),"status":"PAUSED"},"updateMask":"status"})
            log.append(("pause","keyword",x["ad_group_criterion.keyword.text"],
                        "generic permit-type query - form/template seekers")); npause+=1
    r=await c.mutate("ad_group_criterion",ops,validate_only=V)
    print(f"[2a] re-enable {len(ENABLE)}, pause broad + {npause} generic PTW terms -> {len(r.get('results',[]))}")
    for k,t,w in ENABLE: log.append(("enable","keyword",t,w))
    log.append(("pause","keyword","smart site safety system (BROAD)",
                "pulled scheme-research and hardware queries"))

    ops=[{"create":{"adGroup":R("adGroups",ag),"status":"ENABLED",
          "keyword":{"text":t,"matchType":mt},"cpcBidMicros":M(b)}} for ag,t,mt,b in NEW_KW]
    r=await c.mutate("ad_group_criterion",ops,validate_only=V)
    print(f"[2b] new keywords: {len(ops)} -> {len(r.get('results',[]))}")
    for ag,t,mt,b in NEW_KW: log.append(("new","keyword",f"{t} [{mt}]",f"bid HK${b:.2f}"))

    # ---------- STAGE 3: negatives -------------------------------------
    have={x.get("campaign_criterion.keyword.text","").lower()
          for x in await c.search("SELECT campaign.id, campaign_criterion.keyword.text "
            f"FROM campaign_criterion WHERE campaign.id={CAMP} AND campaign_criterion.negative=TRUE")}
    ops=[]; added=0
    for theme,terms in NEG.items():
        for t in terms:
            if t.lower() in have: continue
            ops.append({"create":{"campaign":R("campaigns",CAMP),"negative":True,
                        "keyword":{"text":t,"matchType":"PHRASE"}}})
            log.append(("negative",theme,t,"phrase")); added+=1
    r=await c.mutate("campaign_criterion",ops,validate_only=V)
    print(f"[3] campaign negatives: {added} new across {len(NEG)} themes -> {len(r.get('results',[]))}")

    # ---------- STAGE 4: repair the two revived PTW ads -----------------
    ads=await c.search("SELECT ad_group.id, ad_group_ad.ad.id, "
      "ad_group_ad.ad.responsive_search_ad.headlines, "
      "ad_group_ad.ad.responsive_search_ad.descriptions, ad_group_ad.ad.final_urls "
      f"FROM ad_group_ad WHERE ad_group.id={AG_PTW} AND ad_group_ad.status='ENABLED'")
    ops=[]
    for a in ads:
        aid=str(a["ad_group_ad.ad.id"])
        hs=[dict(h) for h in a["ad_group_ad.ad.responsive_search_ad.headlines"]]
        ds=[dict(x) for x in a["ad_group_ad.ad.responsive_search_ad.descriptions"]]
        for coll,rep,fld in ((hs,PTW_H.get(aid,{}),"headline"),(ds,PTW_D.get(aid,{}),"description")):
            miss=[o for o in rep if not any(i.get("text")==o for i in coll)]
            if miss: print(f"  !! ad {aid} {fld}: source not found {miss}"); return
            for item in coll:
                if item.get("text") in rep:
                    n=rep[item["text"]]
                    log.append(("ad copy",f"ad {aid}",item["text"],n)); item["text"]=n
        txt=[h["text"] for h in hs]
        dup=[t for t in set(txt) if txt.count(t)>1]
        if dup: print(f"  !! ad {aid} duplicate headlines {dup}"); return
        for need in ("500+ Projects Worldwide","200+ Safety Modules"):
            if need not in txt: print(f"  !! ad {aid} missing mandatory {need!r}"); return
        ops.append({"update":{"resourceName":R("ads",aid),
            "responsiveSearchAd":{"headlines":hs,"descriptions":ds},"finalUrls":[PTW_URL]},
            "updateMask":"responsive_search_ad.headlines,responsive_search_ad.descriptions,final_urls"})
        log.append(("url",f"ad {aid}","hardcoded UTM query string",PTW_URL))
    r=await c.mutate("ad",ops,validate_only=V)
    print(f"[4] PTW ad repairs: {len(ops)} ads -> {len(r.get('results',[]))}")

    # ---------- STAGE 5: new assets on the live 4S ad group -------------
    made={}
    sl=await c.mutate("asset",[{"create":{"name":lt,"finalUrls":[u],
        "sitelinkAsset":{"linkText":lt,"description1":d1,"description2":d2}}}
        for lt,d1,d2,u in SITELINKS],validate_only=V)
    for (lt,*_),x in zip(SITELINKS,sl.get("results",[])):
        made[lt]=x.get("resourceName","").rsplit("/",1)[-1] or None
    want={t:None for t in CALLOUTS}
    for x in await c.search("SELECT asset.id, asset.callout_asset.callout_text FROM asset "
      "WHERE asset.type='CALLOUT' AND asset.callout_asset.callout_text IN ("
      + ",".join(f"'{t}'" for t in CALLOUTS) + ")"):
        want.setdefault(x["asset.callout_asset.callout_text"])
        if want.get(x["asset.callout_asset.callout_text"]) is None:
            want[x["asset.callout_asset.callout_text"]]=str(x["asset.id"])
    miss=[t for t,v in want.items() if not v]
    if miss:
        rr=await c.mutate("asset",[{"create":{"name":t,"calloutAsset":{"calloutText":t}}}
                                   for t in miss],validate_only=V)
        for t,x in zip(miss,rr.get("results",[])):
            want[t]=x.get("resourceName","").rsplit("/",1)[-1] or None
    h,vals=SNIPPET
    sn=await c.mutate("asset",[{"create":{"name":f"Snippet - {h}",
        "structuredSnippetAsset":{"header":h,"values":vals}}}],validate_only=V)
    snid=(sn.get("results") or [{}])[0].get("resourceName","").rsplit("/",1)[-1] or None
    links=[]
    for lt,*_ in SITELINKS:
        if made.get(lt): links.append({"create":{"adGroup":R("adGroups",AG_4S),
            "asset":R("assets",made[lt]),"fieldType":"SITELINK"}})
        log.append(("new asset","sitelink",lt,"enterprise / commercial-stage"))
    for t in CALLOUTS:
        if want.get(t): links.append({"create":{"adGroup":R("adGroups",AG_4S),
            "asset":R("assets",want[t]),"fieldType":"CALLOUT"}})
        log.append(("new asset","callout",t,"verified capability or approved claim"))
    if snid: links.append({"create":{"adGroup":R("adGroups",AG_4S),
        "asset":R("assets",snid),"fieldType":"STRUCTURED_SNIPPET"}})
    log.append(("new asset","structured snippet",f"{h}: {', '.join(vals)}","platform breadth"))
    if links:
        r=await c.mutate("ad_group_asset",links,validate_only=V)
        print(f"[5] new assets linked: {len(links)} -> {len(r.get('results',[]))}")
    else:
        print("[5] asset links deferred to apply run (ids only exist after real creates)")

    print("\n"+"="*78)
    for x in log: print(" | ".join(str(i) for i in x))
    print(f"\n{len(log)} changes {'APPLIED' if APPLY else 'PREVIEWED'}")
    json.dump([list(map(str,x)) for x in log],
      open("/tmp/claude-0/-home-user-viact-ads-manager/26274bcb-f27c-5cac-bbc0-c9360bacb908/scratchpad/opt_log.json","w"),indent=1)

asyncio.run(main())
