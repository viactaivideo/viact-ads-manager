"""End-to-end claim cleanup across active Search and PMax campaigns.

Removal categories (established in docs/BRAND_CLAIMS.md):
  SUPERIORITY  No.1 / Best / Top / Leading / Most / World's
  ABSOLUTE     100% / Guarantee / Zero Blind Spot
  STATISTIC    any %, x-multiple performance claim with no substantiation
  ENDORSEMENT  claims a body approved the product
Correction category:
  CANON        a projects/modules count that varies from the approved wording

Unverified counts with no canonical form (25+ Countries, 50+ Singapore
Projects, 100+ SG Contractors, 7+ Years, "Trusted by ...") are FLAGGED and
left in place - guessing a replacement value is worse than reporting it.
"""
import asyncio, json, sys
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config

CID="3767588103"; APPLY="--apply" in sys.argv
R=lambda s,*i: f"customers/{CID}/{s}/" + "~".join(str(x) for x in i)

# ---------------------------------------------------------------- RSA edits
HEADLINES={  # ad id -> {old: new}
 "757431020304":{"Best Construction Safety App":"Detect Site Hazards Live",
                 "Singapore's Leading VSS":"AI Video Analytics VSS",
                 "‎Singapore MOM Compliant":"Automate Safety Reporting"},
 "797860419081":{"Singapore's Leading AI VSS":"Automate Site Compliance"},
 "806829809517":{"90% Fewer Vehicle Incidents":"Reduce Vehicle Incidents",
                 "Trusted by Top SG Fleets":"Built For SG Heavy Fleets"},
}
DESCRIPTIONS={
 "780076309642":{"ePTW & 4S Integrated. Auto Incident Reports. 100% Safety Compliance.":
                 "ePTW & 4S Integrated. Auto Incident Reports. 200+ Safety Modules."},
 "813415085758":{"Complete 4S Platform With Lowest Price Guarantee For Hong Kong Projects":
                 "Complete 4S Platform Built For Hong Kong Construction Projects"},
 "797860419081":{"Most Awarded AI Solution Built For Singapore Construction & Infrastructure Projects.":
                 "AI Safety Platform Built For Singapore Construction & Infrastructure Projects.",
                 "AI CCTV VSS With Real-Time Risk Prevention Alert. Proven 90% Reduction in Safety Breaches.":
                 "AI CCTV VSS With Real-Time Risk Prevention Alerts. 500+ Projects Worldwide."},
 "806458107540":{"Reduce Manual Inspections By Up To 90% With AI Site Monitoring":
                 "Reduce Manual Inspection Effort With Continuous AI Site Monitoring"},
 "806829809517":{"Cut vehicle incidents 90% with viAct AI fleet safety platform. Book a demo today.":
                 "Reduce vehicle incidents with the viAct AI fleet safety platform. Book a demo today.",
                 "Save lives, cut downtime, pass MOM audits. Onboard AI for heavy-industry fleets.":
                 "Cut downtime and support MOM audit readiness. AI for heavy-industry fleets."},
}

# ------------------------------------------------------- PMax asset groups
# (asset_group, field_type, asset_id, old text, replacement text or None)
PMAX=[
 ("6686105845","LONG_HEADLINE","374679139637",
  "Complete 4S Platform With Lowest Price Guarantee For Hong Kong Projects",
  "Complete 4S Platform Built For Hong Kong Construction Projects"),
 ("6686105845","DESCRIPTION","376639986219",
  "Complete 4S Coverage With A Lowest Price Guarantee For HK Contractors.",
  "Complete 4S Coverage For Hong Kong Contractors, CITF Listed And 4S Label Ready."),
 ("6686105845","DESCRIPTION","376639986228",
  "Trusted On 400+ Projects For Enterprise Safety And Risk Management.",
  "Trusted Across 500+ Projects Worldwide For Enterprise Safety And Risk Management."),
 ("6686105845","LONG_HEADLINE","376639986231",
  "Trusted Across 500+ Projects With Enterprise-Wide Safety Management",
  "Trusted Across 500+ Projects Worldwide With Enterprise-Wide Safety Management"),
 ("6616994854","HEADLINE","124768005549","No.1 Construction Surveillance",None),
 ("6616994854","HEADLINE","245280622202","Singapore's Leading VSS",None),
 ("6616994854","HEADLINE","318655918789","MOM-Approved Site VSS",None),
 ("6616994854","LONG_HEADLINE","287041116514",
  "Most Advanced VSS, Adopted by Singapore's Leading Real Estate Developers and Contractors",None),
 ("6616994854","LONG_HEADLINE","362717842548","No.1 AI-enabled Construction VSS",None),
 ("6616994854","DESCRIPTION","131808933047",
  "Best Construction Safety App in Singapore: 90% Less Accidents in first 2 Weeks with AI",
  "AI Construction Safety Platform For Singapore Sites. 500+ Projects Worldwide."),
 ("6616994854","DESCRIPTION","131808933053",
  "Zero Blind Spot: PPE Monitoring, Height Work Safety, Missing Barricades & 100+ AI Modules",
  "PPE Monitoring, Height Work Safety, Missing Barricades And 200+ Safety Modules."),
]

# ------------------------------------------------------------- callouts
# level, owner id, [(asset_id, old text)], [new callout text]
CALLOUTS=[
 ("customer",None,[("335781062730","200+ Smart Safety Rules"),
                   ("335781062736","500+ Global Projects")],
  ["200+ Safety Modules"]),
 ("campaign","22135492526",[("316726584767","90% Fewer Accidents"),
                            ("316726584770","95% Workflow Clarity"),
                            ("316726584773","90% Less Manual Check")],
  ["Multi-Site Management","Audit-Ready Reports","Real-Time Safety Alerts"]),
 ("campaign","23029018962",[("320850066849","90% Better Monitoring"),
                            ("320850066852","95% Workflow Transparency"),
                            ("320850066855","90% Fewer Accidents"),
                            ("320850066873","No. 1 HK 4S System")],[]),
 ("campaign","23089035315",[("320724258701","No.1 Singapore VSS"),
                            ("320724258707","90% Fewer Breaches"),
                            ("320724258710","60% Faster Reporting"),
                            ("315678954476","200+ AI Safety Modules")],
  ["200+ Safety Modules"]),
 ("ad_group","127207121490",[("316197589908","85% Fewer Accidents"),
                             ("316197589911","95% Better Workflow View"),
                             ("316197589914","70% Cheaper Monitoring"),
                             ("316197589917","10x Lower Insurance Cost")],
  ["Works With Existing CCTV","24/7 Site Monitoring","Real-Time Safety Alerts","Centralized Monitoring"]),
 ("ad_group","181304338060",[("316195561209","90% Fewer Accidents"),
                             ("316195561212","95% Better Workflow View"),
                             ("316195561215","70% Cheaper Monitoring"),
                             ("316195561218","90%+ Accuracy Onsite")],
  ["Works With Existing CCTV","Real-Time Safety Alerts","Multi-Site Management","AI Hazard Detection"]),
 ("ad_group","183031419284",[("316147432792","85% Fewer Accidents"),
                             ("316147432795","95% Better Workflow View"),
                             ("316147432798","70% Cheaper Monitoring"),
                             ("316147432801","10x Lower Insurance Cost")],
  ["Audit-Ready Reports","Digital Permit To Work","Automated Safety Reports","Centralized Monitoring"]),
 ("ad_group","183420975242",[("323318345074","92% Fewer PPE Violations"),
                             ("323318345077","80% Fewer Repeat Breaches"),
                             ("323318345080","10x Audit Readiness")],[]),
 ("ad_group","189327327009",[("328082775652","90% Accident Reduction"),
                             ("328082775655","95% Workflow Transparency"),
                             ("328082775658","90% Better Surveillance")],[]),
 ("ad_group","184036341797",[("323318559538","92% Fewer PPE Violations"),
                             ("323318559541","80% Fewer Repeat Breaches"),
                             ("323318559544","10x Audit Readiness")],[]),
 ("ad_group","182679213480",[("314554640380","100+ AI Safety Modules"),
                             ("317512453984","No.1 VSS Singapore"),
                             ("317512453987","90% Fewer Safety Breaches"),
                             ("317512453990","60% Less Reporting Time")],
  ["200+ Safety Modules","24/7 Site Monitoring","Audit-Ready Reports"]),
 ("ad_group","196542726632",[("354542682801","Cut Incidents by 90%")],
  ["Real-Time Safety Alerts"]),
 ("ad_group","187046817114",[("317557720047","80% Less PPE Violations"),
                             ("317557720050","90% Less Manual Checks"),
                             ("317557720053","10x Audit Readiness")],
  ["AI Hazard Detection","Automated Safety Reports"]),
]

# --------------------------------------------------------------- sitelinks
# ad_group id, old asset id, new sitelink (link_text, d1, d2, url)
SITELINKS=[
 ("127207121490","300261506926","Ensure 100% PPE Compliance",
  ("AI PPE Detection System","Detect PPE Non Compliance","Automate PPE Monitoring",
   "https://www.viact.ai/ppedetection")),
 ("183031419284","303428211161","Leading EHS Platform KSA",
  ("Smart EHS Software Saudi","EHS Compliance Made Simple","AI EHS Platform For KSA",
   "https://www.viact.ai/ehs/ehs-management-software-saudi-arabia")),
 ("183031419284","303428211173","Dubai's Top Safety Platform",
  ("Smart EHS Solution Dubai","AI-Driven EHS Dubai","AI Safety Platform For Dubai",
   "https://www.viact.ai/ehs/ehs-management-software-dubai")),
]

LIMITS={"HEADLINE":30,"LONG_HEADLINE":90,"DESCRIPTION":90}

def check():
    bad=[]
    for aid,m in HEADLINES.items():
        for o,n in m.items():
            if len(n)>30: bad.append(f"headline {n!r} {len(n)}>30")
    for aid,m in DESCRIPTIONS.items():
        for o,n in m.items():
            if len(n)>90: bad.append(f"description {n!r} {len(n)}>90")
    for ag,ft,a,o,n in PMAX:
        if n and len(n)>LIMITS[ft]: bad.append(f"{ft} {n!r} {len(n)}>{LIMITS[ft]}")
    for lvl,own,rem,add in CALLOUTS:
        for t in add:
            if len(t)>25: bad.append(f"callout {t!r} {len(t)}>25")
    for ag,old,why,(lt,d1,d2,u) in SITELINKS:
        if len(lt)>25: bad.append(f"sitelink text {lt!r}")
        if len(d1)>35 or len(d2)>35: bad.append(f"sitelink desc {d1!r}/{d2!r}")
    return bad


async def main():
    bad=check()
    if bad:
        print("LENGTH/VALIDATION FAILURES — nothing sent:"); [print("  ",b) for b in bad]; return
    c=GoogleAdsClient(load_config())
    log=[]

    # ---- 1. responsive search ads -------------------------------------
    ads=await c.search("SELECT ad_group_ad.ad.id, campaign.name, ad_group.name, "
      "ad_group_ad.ad.responsive_search_ad.headlines, "
      "ad_group_ad.ad.responsive_search_ad.descriptions "
      "FROM ad_group_ad WHERE campaign.status='ENABLED' AND ad_group.status='ENABLED' "
      "AND ad_group_ad.status='ENABLED' AND campaign.advertising_channel_type='SEARCH'")
    ad_ops=[]
    for a in ads:
        aid=str(a["ad_group_ad.ad.id"])
        if aid not in HEADLINES and aid not in DESCRIPTIONS: continue
        hs=[dict(h) for h in a["ad_group_ad.ad.responsive_search_ad.headlines"]]
        ds=[dict(x) for x in a["ad_group_ad.ad.responsive_search_ad.descriptions"]]
        mask=[]
        for coll,rep,fld in ((hs,HEADLINES.get(aid,{}),"headlines"),
                             (ds,DESCRIPTIONS.get(aid,{}),"descriptions")):
            missing=[o for o in rep if not any(i.get("text")==o for i in coll)]
            if missing:
                print(f"  !! ad {aid} {fld}: source text not found {missing}"); return
            hit=False
            for item in coll:
                if item.get("text") in rep:
                    new=rep[item["text"]]
                    log.append((a["campaign.name"],a["ad_group.name"],f"ad {aid}",
                                fld[:-1],item["text"],new))
                    item["text"]=new; hit=True
            if hit: mask.append(f"responsive_search_ad.{fld}")
        texts=[h["text"] for h in hs]
        dup=[t for t in set(texts) if texts.count(t)>1]
        if dup: print(f"  !! ad {aid} duplicate headlines after edit: {dup}"); return
        ad_ops.append({"update":{"resourceName":R("ads",aid),
            "responsiveSearchAd":{"headlines":hs,"descriptions":ds}},
            "updateMask":",".join(mask)})
    print(f"\n[1] responsive search ads: {len(ad_ops)} updates")
    if ad_ops:
        r=await c.mutate("ad", ad_ops, validate_only=not APPLY)
        print("   ", "APPLIED" if APPLY else "VALIDATED", len(r.get("results",[])) or "ok")

    # ---- 2. PMax asset groups -----------------------------------------
    new_ids={}
    creates=[{"create":{"textAsset":{"text":n}}} for _,_,_,_,n in PMAX if n]
    if creates:
        r=await c.mutate("asset", creates, validate_only=not APPLY)
        made=[x.get("resourceName","") for x in r.get("results",[])]
        for (n,rn) in zip([n for *_,n in PMAX if n], made):
            new_ids[n]=rn.rsplit("/",1)[-1] if rn else None
    ag_ops=[]
    for ag,ft,aid,old,new in PMAX:
        ag_ops.append({"remove":R("assetGroupAssets",ag,aid,ft)})
        log.append((f"asset group {ag}",ft,aid,"remove",old,new or "(removed, not replaced)"))
        if new and new_ids.get(new):
            ag_ops.append({"create":{"assetGroup":R("assetGroups",ag),
                "asset":R("assets",new_ids[new]),"fieldType":ft}})
    print(f"\n[2] PMax asset group assets: {len(creates)} new texts, {len(ag_ops)} link ops")
    if APPLY and ag_ops:
        r=await c.mutate("asset_group_asset", ag_ops, validate_only=False)
        print("    APPLIED", len(r.get("results",[])))
    elif ag_ops:
        print("    (link ops need real asset ids; validated on apply)")

    # ---- 3. callouts ---------------------------------------------------
    want=sorted({t for _,_,_,add in CALLOUTS for t in add})
    have={}
    if want:
        q=("SELECT asset.id, asset.callout_asset.callout_text FROM asset "
           "WHERE asset.type='CALLOUT' AND asset.callout_asset.callout_text IN "
           "(" + ",".join(f"'{t}'" for t in want) + ")")
        for x in await c.search(q):
            have.setdefault(x["asset.callout_asset.callout_text"], str(x["asset.id"]))
    missing=[t for t in want if t not in have]
    if missing:
        r=await c.mutate("asset",[{"create":{"name":t,"calloutAsset":{"calloutText":t}}}
                                  for t in missing], validate_only=not APPLY)
        for t,x in zip(missing, r.get("results",[])):
            have[t]=x.get("resourceName","").rsplit("/",1)[-1] or None
    print(f"\n[3] callouts: {len(want)} texts needed, {len(missing)} newly created")
    by_lvl={"customer":[],"campaign":[],"ad_group":[]}
    for lvl,own,rem,add in CALLOUTS:
        res={"customer":"customerAssets","campaign":"campaignAssets","ad_group":"adGroupAssets"}[lvl]
        for aid,old in rem:
            ids=(aid,"CALLOUT") if lvl=="customer" else (own,aid,"CALLOUT")
            by_lvl[lvl].append({"remove":R(res,*ids)})
            log.append((lvl,own or "account","callout",aid,old,"(removed)"))
        for t in add:
            if not have.get(t): continue
            payload={"asset":R("assets",have[t]),"fieldType":"CALLOUT"}
            if lvl=="campaign": payload["campaign"]=R("campaigns",own)
            if lvl=="ad_group": payload["adGroup"]=R("adGroups",own)
            by_lvl[lvl].append({"create":payload})
            log.append((lvl,own or "account","callout","new",f"(added) {t}",""))
    for lvl,ops in by_lvl.items():
        if not ops: continue
        print(f"    {lvl}: {len(ops)} ops")
        if APPLY:
            r=await c.mutate(f"{lvl}_asset", ops, validate_only=False)
            print("      APPLIED", len(r.get("results",[])))

    # ---- 4. sitelinks --------------------------------------------------
    sl_ids={}
    if SITELINKS:
        r=await c.mutate("asset",[{"create":{"name":lt,"finalUrls":[u],
            "sitelinkAsset":{"linkText":lt,"description1":d1,"description2":d2}}}
            for _,_,_,(lt,d1,d2,u) in SITELINKS], validate_only=not APPLY)
        for (ag,old,why,(lt,*_)),x in zip(SITELINKS, r.get("results",[])):
            sl_ids[old]=x.get("resourceName","").rsplit("/",1)[-1] or None
    sl_ops=[]
    for ag,old,why,(lt,d1,d2,u) in SITELINKS:
        sl_ops.append({"remove":R("adGroupAssets",ag,old,"SITELINK")})
        log.append(("ad_group",ag,"sitelink",old,why,f"(replaced) {d1} / {d2}"))
        if sl_ids.get(old):
            sl_ops.append({"create":{"adGroup":R("adGroups",ag),
                "asset":R("assets",sl_ids[old]),"fieldType":"SITELINK"}})
    print(f"\n[4] sitelinks: {len(SITELINKS)} replaced, {len(sl_ops)} link ops")
    if APPLY and sl_ops:
        r=await c.mutate("ad_group_asset", sl_ops, validate_only=False)
        print("    APPLIED", len(r.get("results",[])))

    print("\n"+"="*76)
    for row in log: print(" | ".join(str(x) for x in row))
    print(f"\n{len(log)} changes {'APPLIED' if APPLY else 'PREVIEWED'}")
    json.dump([list(map(str,r)) for r in log],
      open("/tmp/claude-0/-home-user-viact-ads-manager/26274bcb-f27c-5cac-bbc0-c9360bacb908/scratchpad/cleanup_log.json","w"),indent=1)

asyncio.run(main())
