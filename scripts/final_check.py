# -*- coding: utf-8 -*-
import asyncio, re, collections
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config
CAMP="22972642686"; AG="189327327009"
FAIL=[]
def chk(ok,msg):
    print(("  OK  " if ok else "  FAIL")+" "+msg)
    if not ok: FAIL.append(msg)
BAN=re.compile(r"\bcitf\b|\bdwss\b|works supervision|\d+\s?%|\b\d+x\b|\bno\.?\s?1\b|"
               r"\bbest\b|\bleading\b|\btop\b|\bguarantee\b|100\s?%|\bmost \w+", re.I)
async def m():
    c=GoogleAdsClient(load_config())
    print("=== SITELINKS ON LIVE 4S AD GROUP ===")
    sl=await c.search("SELECT ad_group.id, ad_group.status, campaign.id, asset.id, "
      "asset.sitelink_asset.link_text, asset.sitelink_asset.description1, "
      "asset.sitelink_asset.description2, asset.final_urls, ad_group_asset.status "
      f"FROM ad_group_asset WHERE ad_group.id={AG} AND ad_group_asset.field_type='SITELINK' "
      "AND ad_group_asset.status='ENABLED'")
    txt=[s.get("asset.sitelink_asset.link_text") for s in sl]
    dup=[t for t in set(txt) if txt.count(t)>1]
    dests=[(s.get("asset.final_urls") or [""])[0].split("?")[0] for s in sl]
    ddup=[d for d in set(dests) if dests.count(d)>1]
    nodesc=[s.get("asset.sitelink_asset.link_text") for s in sl
            if not s.get("asset.sitelink_asset.description1")]
    chk(not dup, f"{len(sl)} sitelinks, duplicate link texts: {dup or 'none'}")
    chk(not ddup, f"duplicate destinations: {ddup or 'none'}")
    chk(not nodesc, f"sitelinks missing descriptions: {nodesc or 'none'}")
    for s in sorted(sl,key=lambda z:z.get("asset.sitelink_asset.link_text") or ""):
        u=(s.get("asset.final_urls") or [""])[0]
        print(f"       [{s.get('asset.sitelink_asset.link_text')}] "
              f"{s.get('asset.sitelink_asset.description1')} / {s.get('asset.sitelink_asset.description2')}"
              + ("   <UTM in URL>" if "?" in u else ""))
    print("\n=== BANNED LANGUAGE SWEEP: every enabled asset on this campaign ===")
    hits=[]
    for s in sl:
        for f in ("asset.sitelink_asset.link_text","asset.sitelink_asset.description1",
                  "asset.sitelink_asset.description2"):
            v=s.get(f)
            if v and BAN.search(v): hits.append(("sitelink",s["asset.id"],v))
    for lvl,res in (("ad group","ad_group_asset"),("campaign","campaign_asset")):
        q=("SELECT campaign.id, asset.id, asset.type, asset.callout_asset.callout_text, "
           "asset.structured_snippet_asset.header, asset.structured_snippet_asset.values, "
           f"{res}.status FROM {res} WHERE campaign.id={CAMP} AND {res}.status='ENABLED'")
        if res=="ad_group_asset": q=q.replace("FROM","").replace(f"{res}.status,",f"{res}.status, ad_group.status,").replace("  "," ")
        q=("SELECT campaign.id, ad_group.status, asset.id, asset.type, asset.callout_asset.callout_text, "
           "asset.structured_snippet_asset.header, asset.structured_snippet_asset.values, "
           f"{res}.status FROM {res} WHERE campaign.id={CAMP} AND {res}.status='ENABLED'") if res=="ad_group_asset" else \
          ("SELECT campaign.id, asset.id, asset.type, asset.callout_asset.callout_text, "
           "asset.structured_snippet_asset.header, asset.structured_snippet_asset.values, "
           f"{res}.status FROM {res} WHERE campaign.id={CAMP} AND {res}.status='ENABLED'")
        for x in await c.search(q):
            for v in ([x.get("asset.callout_asset.callout_text")]
                      + (x.get("asset.structured_snippet_asset.values") or [])
                      + [x.get("asset.structured_snippet_asset.header")]):
                if v and BAN.search(v): hits.append((f"{lvl} {x['asset.type']}",x["asset.id"],v))
    ads=await c.search("SELECT ad_group.id, ad_group.name, ad_group.status, ad_group_ad.ad.id, "
      "ad_group_ad.ad.responsive_search_ad.headlines, "
      "ad_group_ad.ad.responsive_search_ad.descriptions "
      f"FROM ad_group_ad WHERE campaign.id={CAMP} AND ad_group_ad.status='ENABLED' "
      "AND ad_group.status='ENABLED'")
    for a in ads:
        for coll in ("headlines","descriptions"):
            for it in a[f"ad_group_ad.ad.responsive_search_ad.{coll}"]:
                t=it["text"]
                if t in ("500+ Projects Worldwide","200+ Safety Modules"): continue
                if BAN.search(t): hits.append((f"ad {a['ad_group_ad.ad.id']} {coll[:-1]}","",t))
    known={"CITF Listed Tech"}   # pre-existing, owner asked to hold pending verification
    real=[h for h in hits if h[2] not in known]
    chk(not real, f"banned-language hits (excluding the held CITF callout): {len(real)}")
    for h in real: print("       ",h)
    held=[h for h in hits if h[2] in known]
    for h in held: print(f"       HELD (your decision, needs verification): {h}")
    print("\n=== MANDATORY HEADLINES ===")
    for a in ads:
        hs=[h["text"] for h in a["ad_group_ad.ad.responsive_search_ad.headlines"]]
        miss=[x for x in ("500+ Projects Worldwide","200+ Safety Modules") if x not in hs]
        d=[t for t in set(hs) if hs.count(t)>1]
        chk(not miss and not d,
            f"ad {a['ad_group_ad.ad.id']} ({a['ad_group.name'][:24]}) "
            + (f"missing={miss} dup={d}" if (miss or d) else "both present, no duplicates"))
    print("\n"+"="*72)
    print(f"{len(FAIL)} FAILURES" if FAIL else "ALL CHECKS PASSED")
    for f in FAIL: print("  -",f)
asyncio.run(m())
