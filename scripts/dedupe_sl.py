# -*- coding: utf-8 -*-
"""Remove duplicate / defective sitelinks from the live HK 4S ad group.

Where two sitelinks share a link text or a destination, the one carrying a
hardcoded UTM query string is dropped: the campaign already appends its own
final-URL suffix, so those links arrive with duplicated utm_source/utm_medium
and mis-attribute in GA4.

Guard: a destination is never left with zero sitelinks. /ppedetection has one
copy with no descriptions and one with hardcoded UTMs, so a clean replacement
is created before either is dropped.
"""
import asyncio, sys, collections
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config
CID="3767588103"; AG="189327327009"; APPLY="--apply" in sys.argv
R=lambda s,*i: f"customers/{CID}/{s}/" + "~".join(str(x) for x in i)
REPLACE=[("PPE Compliance Monitoring","Detect PPE Non Compliance","Automate PPE Monitoring",
          "https://www.viact.ai/ppedetection")]
async def m():
    c=GoogleAdsClient(load_config())
    rows=await c.search("SELECT ad_group.id, ad_group.status, campaign.id, asset.id, "
      "asset.sitelink_asset.link_text, asset.sitelink_asset.description1, "
      "asset.sitelink_asset.description2, asset.final_urls, ad_group_asset.status "
      f"FROM ad_group_asset WHERE ad_group.id={AG} AND ad_group_asset.field_type='SITELINK' "
      "AND ad_group_asset.status='ENABLED'")
    dest=lambda r:(r.get("asset.final_urls") or [""])[0].split("?")[0]
    clean=lambda r:"?" not in (r.get("asset.final_urls") or [""])[0]
    full=lambda r:bool(r.get("asset.sitelink_asset.description1") and r.get("asset.sitelink_asset.description2"))
    drop={}
    def mark(r,why):
        drop[r["asset.id"]]=(r.get("asset.sitelink_asset.link_text"),why,
                             (r.get("asset.final_urls") or [""])[0])
    # rank: clean URL first, then has both descriptions
    for grp in list(collections.defaultdict(list,
            {k:[r for r in rows if r.get("asset.sitelink_asset.link_text")==k]
             for k in {r.get("asset.sitelink_asset.link_text") for r in rows}}).values()):
        if len(grp)<2: continue
        keep=sorted(grp,key=lambda r:(not clean(r),not full(r)))[0]
        for g in grp:
            if g["asset.id"]!=keep["asset.id"]:
                mark(g,"duplicate link text"+(" + hardcoded UTM" if not clean(g) else ""))
    for d,grp in collections.defaultdict(list,
            {k:[r for r in rows if dest(r)==k] for k in {dest(r) for r in rows}}).items():
        survivors=[g for g in grp if g["asset.id"] not in drop]
        if len(survivors)<2: continue
        keep=sorted(survivors,key=lambda r:(not clean(r),not full(r)))[0]
        for g in survivors:
            if g["asset.id"]!=keep["asset.id"]:
                mark(g,"duplicate destination"+(" + hardcoded UTM" if not clean(g) else ""))
    # a sitelink with no descriptions is dropped only if its destination keeps cover
    for r in rows:
        if r["asset.id"] in drop or full(r): continue
        others=[g for g in rows if dest(g)==dest(r) and g["asset.id"]!=r["asset.id"]
                and g["asset.id"] not in drop]
        new_cover=any(u.split("?")[0]==dest(r) for _,_,_,u in REPLACE)
        if others or new_cover: mark(r,"no descriptions - wastes SERP space")
        else: print(f"  KEEP {r['asset.id']} [{r.get('asset.sitelink_asset.link_text')}] "
                    f"- thin, but it is the only link to {dest(r)}")
    print(f"\n{len(rows)} enabled sitelinks | dropping {len(drop)} | adding {len(REPLACE)} "
          f"| final {len(rows)-len(drop)+len(REPLACE)}\n")
    for aid,(lt,why,u) in drop.items():
        print(f"  DROP {aid}  [{lt}]  {why}\n       {u[:110]}")
    for lt,d1,d2,u in REPLACE: print(f"  ADD  [{lt}]  {d1} / {d2}\n       {u}")
    # guard: no destination may end with zero sitelinks
    left=collections.Counter(dest(r) for r in rows if r["asset.id"] not in drop)
    for _,_,_,u in REPLACE: left[u.split("?")[0]]+=1
    gone=[dest(r) for r in rows if not left.get(dest(r))]
    if gone: print(f"\nABORT: these destinations would lose every sitelink: {set(gone)}"); return
    if len(rows)-len(drop)+len(REPLACE) < 4: print("\nABORT: fewer than 4 sitelinks."); return
    V=not APPLY
    rr=await c.mutate("asset",[{"create":{"name":lt,"finalUrls":[u],
        "sitelinkAsset":{"linkText":lt,"description1":d1,"description2":d2}}}
        for lt,d1,d2,u in REPLACE],validate_only=V)
    ops=[]
    for (lt,*_),x in zip(REPLACE,rr.get("results",[])):
        nid=x.get("resourceName","").rsplit("/",1)[-1]
        if nid: ops.append({"create":{"adGroup":R("adGroups",AG),
            "asset":R("assets",nid),"fieldType":"SITELINK"}})
    ops+=[{"remove":R("adGroupAssets",AG,aid,"SITELINK")} for aid in drop]
    r=await c.mutate("ad_group_asset",ops,validate_only=V)
    print(f"\n{'APPLIED' if APPLY else 'VALIDATED'} {len(r.get('results',[]))} of {len(ops)} ops")
asyncio.run(m())
