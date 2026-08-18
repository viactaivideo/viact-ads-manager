# -*- coding: utf-8 -*-
"""Rebuild the ePTW ad group's sitelinks and drop its one benefit statistic.

All 12 inherited sitelinks were bare link text with no descriptions, and most
pointed at industry pages unrelated to permit-to-work intent. Replacements are
created and linked BEFORE any removal so the ad group is never left bare.
"""
import asyncio, sys
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config
CID="3767588103"; AG="195039132719"; APPLY="--apply" in sys.argv
R=lambda s,*i: f"customers/{CID}/{s}/" + "~".join(str(x) for x in i)
NEW=[
 ("Book An ePTW Demo","See Digital Permits Live","Talk To A Permit Specialist",
  "https://www.viact.ai/demo"),
 ("Digital Permit To Work","Paperless Permit Approvals","Approve Permits On Mobile",
  "https://www.viact.ai/permit-to-work-software"),
 ("Confined Space Permits","Monitor Confined Space Entry","AI Confined Space Safety",
  "https://www.viact.ai/confined-space-safety-monitoring"),
 ("Area Control System","Prevent Unauthorized Entry","Control High-Risk Zones",
  "https://www.viact.ai/solutions/area-control-safety-system"),
 ("Centralised Site Platform","One Dashboard, Every Site","Access Anytime, Anywhere",
  "https://www.viact.ai/vihub"),
 ("Talk To Our Sales Team","Discuss Scope And Rollout","Speak With A Specialist",
  "https://www.viact.ai/contactsales"),
]
DROP_CALLOUT=[("351970400549","7 Hours Saved Per Day")]
def validate():
    bad=[]
    seen=set()
    for lt,d1,d2,u in NEW:
        if len(lt)>25: bad.append(f"link text {lt!r} {len(lt)}>25")
        for d in (d1,d2):
            if len(d)>35: bad.append(f"desc {d!r} {len(d)}>35")
        if "?" in u or not u.startswith("https://www.viact.ai/"): bad.append(f"url {u}")
        if lt in seen: bad.append(f"duplicate link text {lt!r}")
        seen.add(lt)
    return bad
async def m():
    bad=validate()
    if bad: print("VALIDATION FAILED:"); [print("  ",b) for b in bad]; return
    c=GoogleAdsClient(load_config()); V=not APPLY
    old=await c.search("SELECT campaign.id, ad_group.id, ad_group.status, asset.id, "
      "asset.sitelink_asset.link_text, asset.sitelink_asset.description1, "
      f"ad_group_asset.field_type, ad_group_asset.status FROM ad_group_asset WHERE ad_group.id={AG} "
      "AND ad_group_asset.field_type='SITELINK' AND ad_group_asset.status='ENABLED'")
    thin=[x for x in old if not x.get("asset.sitelink_asset.description1")]
    print(f"existing sitelinks {len(old)} | without descriptions {len(thin)} | adding {len(NEW)}")
    print(f"final count would be {len(old)-len(thin)+len(NEW)}")
    if len(old)-len(thin)+len(NEW) < 4: print("ABORT"); return
    rr=await c.mutate("asset",[{"create":{"name":lt,"finalUrls":[u],
        "sitelinkAsset":{"linkText":lt,"description1":d1,"description2":d2}}}
        for lt,d1,d2,u in NEW],validate_only=V)
    links=[]
    for (lt,*_),x in zip(NEW,rr.get("results",[])):
        nid=x.get("resourceName","").rsplit("/",1)[-1]
        if nid: links.append({"create":{"adGroup":R("adGroups",AG),
            "asset":R("assets",nid),"fieldType":"SITELINK"}})
    if links:
        r=await c.mutate("ad_group_asset",links,validate_only=V)
        print(f"  created + linked {len(r.get('results',[]))} sitelinks")
    rem=[{"remove":R("adGroupAssets",AG,x["asset.id"],"SITELINK")} for x in thin]
    rem+=[{"remove":R("adGroupAssets",AG,a,"CALLOUT")} for a,_ in DROP_CALLOUT]
    r=await c.mutate("ad_group_asset",rem,validate_only=V)
    print(f"  removed {len(r.get('results',[]))} of {len(rem)} "
          f"({len(thin)} bare sitelinks + {len(DROP_CALLOUT)} statistic callout)")
    for lt,d1,d2,u in NEW: print(f"    ADD  [{lt}] {d1} / {d2}")
    for a,t in DROP_CALLOUT: print(f"    DROP callout {a} {t!r}")
asyncio.run(m())
