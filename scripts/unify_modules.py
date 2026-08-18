# -*- coding: utf-8 -*-
"""Bring every platform module-count claim onto the approved wording.

Instruction 18 Aug 2026: "200+ Smart Safety Rules & 200+ Safety Modules are
same. So replace ... every where or any similar headlines, or descriptions or
any ad asset." Scope is therefore ALL statuses, not just serving units - the
earlier enabled-only rule does not apply to this one.

NOT touched, because they say something different: "Free Platform & 2 AI
Modules", "14Days Freemium +2 AI module" and "Try Our 2 AI Modules" describe
what a free trial includes, not how many modules the platform has. Rewriting
those to 200+ would change their meaning, not standardise it.
"""
import asyncio, sys, re
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config
CID="3767588103"; APPLY="--apply" in sys.argv
R=lambda s,*i: f"customers/{CID}/{s}/" + "~".join(str(x) for x in i)
CANON="200+ Safety Modules"; CANON_ASSET="354541291920"
# headline wordings that mean "the platform has N modules"
H_VARIANTS={"200+ Smart Safety Rules","200+ AI Safety Modules","200+ Ai Safety Modules",
            "100+ Pre-Built AI Modules","100+ AI Modules","200+ Safety Rules"}
# descriptions need a rewrite, not a swap
D_REWRITE={
 "100+ AI models to help in monitoring health and safety related complainces automatically.":
   "200+ Safety Modules to monitor health and safety compliance automatically.",
 "30 AI modules to enhance construction worker safety and productivity with site environment":
   "200+ Safety Modules to enhance construction worker safety and site productivity.",
 "100+ Pre-Built AI Modules to monitor PPE, Intrusion, Barricades, Worker Machine Proximity.":
   "200+ Safety Modules to monitor PPE, Intrusion, Barricades and Worker Machine Proximity.",
 "Zero Blind Spot: PPE Monitoring, Height Work Safety, Missing Barricades & 100+ AI Modules":
   "PPE Monitoring, Height Work Safety, Missing Barricades And 200+ Safety Modules.",
 "Zero Blind Spot, PPE Monitoring, Height Work Safety, Missing Barricades & 100+ AI Modules":
   "PPE Monitoring, Height Work Safety, Missing Barricades And 200+ Safety Modules.",
}
FLAG=[]
async def main():
    for k,v in D_REWRITE.items():
        assert len(v)<=90, (v,len(v))
    assert len(CANON)<=30
    c=GoogleAdsClient(load_config()); V=not APPLY; plan=[]

    # ---------------- search ads (every status) ----------------
    ads=await c.search("SELECT campaign.name, campaign.status, ad_group.name, ad_group.status, "
      "ad_group_ad.status, ad_group_ad.ad.id, ad_group_ad.ad.responsive_search_ad.headlines, "
      "ad_group_ad.ad.responsive_search_ad.descriptions FROM ad_group_ad "
      "WHERE ad_group_ad.status!='REMOVED'")
    ops=[]
    for a in ads:
        aid=str(a["ad_group_ad.ad.id"])
        hs=[dict(h) for h in a.get("ad_group_ad.ad.responsive_search_ad.headlines") or []]
        ds=[dict(d) for d in a.get("ad_group_ad.ad.responsive_search_ad.descriptions") or []]
        if not hs: continue
        mask=[]; touched=False
        for h in hs:
            if h.get("text") in H_VARIANTS:
                if any(o.get("text")==CANON for o in hs if o is not h):
                    FLAG.append((aid,a["campaign.name"],h["text"],
                                 "ad already carries the approved wording - a swap would duplicate it"))
                    continue
                plan.append((f"{a['campaign.name']} / {a['ad_group.name']}",f"ad {aid} headline",
                             h["text"],CANON,a["campaign.status"],a["ad_group.status"],a["ad_group_ad.status"]))
                h["text"]=CANON; touched=True
            elif re.search(r"\bAI\s*Module|模組|準確率",h.get("text",""),re.I) and h["text"] not in H_VARIANTS:
                FLAG.append((aid,a["campaign.name"],h["text"],
                             "different claim or non-English copy - needs your wording, not a guess"))
        if touched: mask.append("responsive_search_ad.headlines")
        touched=False
        for d in ds:
            if d.get("text") in D_REWRITE:
                new=D_REWRITE[d["text"]]
                if any(o.get("text")==new for o in ds if o is not d):
                    FLAG.append((aid,a["campaign.name"],d["text"],"rewrite would duplicate another description"))
                    continue
                plan.append((f"{a['campaign.name']} / {a['ad_group.name']}",f"ad {aid} description",
                             d["text"],new,a["campaign.status"],a["ad_group.status"],a["ad_group_ad.status"]))
                d["text"]=new; touched=True
        if touched: mask.append("responsive_search_ad.descriptions")
        if not mask: continue
        txt=[h["text"] for h in hs]
        dup=[t for t in set(txt) if txt.count(t)>1]
        if dup: print(f"  !! ad {aid} would end with duplicate headlines {dup}"); return
        ops.append({"update":{"resourceName":R("ads",aid),
            "responsiveSearchAd":{"headlines":hs,"descriptions":ds}},"updateMask":",".join(mask)})
    print(f"[1] search ads to update: {len(ops)}")
    if ops:
        r=await c.mutate("ad",ops,validate_only=V)
        print(f"    {'APPLIED' if APPLY else 'VALIDATED'} {len(r.get('results',[]))}")

    # ---------------- performance max ----------------
    rows=await c.search("SELECT campaign.name, campaign.status, asset_group.id, asset_group.name, "
      "asset_group.status, asset_group_asset.field_type, asset_group_asset.status, asset.id, "
      "asset.text_asset.text FROM asset_group_asset WHERE asset_group_asset.status!='REMOVED'")
    have=set()
    for x in rows:
        if x.get("asset.text_asset.text")==CANON and x["asset_group_asset.status"]=="ENABLED":
            have.add(x["asset_group.id"])
    pm=[]; newtext={}
    for x in rows:
        t=x.get("asset.text_asset.text"); ft=x["asset_group_asset.field_type"]
        if x["asset_group_asset.status"]!="ENABLED" or not t: continue
        if ft=="HEADLINE" and t in H_VARIANTS:
            pm.append((x,CANON_ASSET,CANON))
        elif ft=="DESCRIPTION" and t in D_REWRITE:
            pm.append((x,None,D_REWRITE[t]))
    creates=[{"create":{"textAsset":{"text":n}}} for x,a,n in pm if a is None]
    if creates:
        rr=await c.mutate("asset",creates,validate_only=V)
        for (x,a,n),res in zip([p for p in pm if p[1] is None],rr.get("results",[])):
            newtext[n]=res.get("resourceName","").rsplit("/",1)[-1] or None
    ops=[]
    for x,a,n in pm:
        gid=x["asset_group.id"]
        ops.append({"remove":R("assetGroupAssets",gid,x["asset.id"],x["asset_group_asset.field_type"])})
        plan.append((f"{x['campaign.name']} / {x['asset_group.name']}",
                     f"PMax {x['asset_group_asset.field_type'].lower()}",x["asset.text_asset.text"],n,
                     x["campaign.status"],x["asset_group.status"],x["asset_group_asset.status"]))
        target=a or newtext.get(n)
        if a and gid in have:
            FLAG.append((gid,x["campaign.name"],x["asset.text_asset.text"],
                         "asset group already carries the approved wording - old variant removed only"))
            continue
        if target:
            ops.append({"create":{"assetGroup":R("assetGroups",gid),
                        "asset":R("assets",target),"fieldType":x["asset_group_asset.field_type"]}})
            if a: have.add(gid)
    print(f"[2] PMax link operations: {len(ops)} ({len(creates)} new description assets)")
    if ops and APPLY:
        r=await c.mutate("asset_group_asset",ops,validate_only=False)
        print(f"    APPLIED {len(r.get('results',[]))}")
    elif ops:
        print("    (link ids only exist after a real create - validated on apply)")

    print(f"\n=== {len(plan)} REPLACEMENTS ===")
    for loc,kind,old,new,cs,gs,as_ in plan:
        live = "LIVE" if cs=="ENABLED" and gs=="ENABLED" and as_=="ENABLED" else "not serving"
        print(f"  [{live:11}] {loc}  |  {kind}")
        print(f"      {old}\n   -> {new}")
    print(f"\n=== {len(FLAG)} FLAGGED, NOT CHANGED ===")
    for f in FLAG: print(f"  {f[1]} ({f[0]}): {f[2]!r}\n      {f[3]}")
asyncio.run(main())
