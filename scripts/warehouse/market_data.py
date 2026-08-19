# -*- coding: utf-8 -*-
"""First-party performance by country for the markets in brief v4."""
import asyncio, collections
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config
FK="23094177252"; D="segments.date BETWEEN '2024-01-01' AND '2026-08-18'"
def n(v):
    try: return float(v)
    except: return 0.0
async def m():
    c=GoogleAdsClient(load_config())
    geo={}
    for x in await c.search("SELECT geo_target_constant.id, geo_target_constant.name "
      "FROM geo_target_constant WHERE geo_target_constant.target_type='Country'"):
        geo[str(x["geo_target_constant.id"])]=x["geo_target_constant.name"]
    print("=== FORKLIFT CAMPAIGN BY COUNTRY (viAct's own data) ===")
    print(f"  {'country':18}{'impr':>8}{'clicks':>8}{'cost HK$':>10}{'conv':>6}{'CPC':>8}{'CTR%':>7}")
    rows=[]
    for x in await c.search("SELECT campaign.id, user_location_view.country_criterion_id, "
      "metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions "
      f"FROM user_location_view WHERE campaign.id={FK} AND {D}"):
        cid=str(x["user_location_view.country_criterion_id"])
        cl=n(x["metrics.clicks"]); co=n(x["metrics.cost_micros"])/1e6; im=n(x["metrics.impressions"])
        rows.append((co,geo.get(cid,cid),im,cl,n(x["metrics.conversions"])))
    for co,name,im,cl,cv in sorted(rows,reverse=True):
        print(f"  {name[:17]:18}{im:>8.0f}{cl:>8.0f}{co:>10,.0f}{cv:>6.1f}"
              f"{co/max(cl,1):>8.1f}{cl/max(im,1)*100:>7.2f}")
    print("\n=== ALL CAMPAIGNS BY COUNTRY, TARGET MARKETS ONLY ===")
    WANT={"United Kingdom","Canada","Australia","Ireland","United States"}
    agg=collections.defaultdict(lambda:[0,0,0.0,0.0])
    for x in await c.search("SELECT campaign.name, user_location_view.country_criterion_id, "
      "metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions "
      f"FROM user_location_view WHERE {D}"):
        nm=geo.get(str(x["user_location_view.country_criterion_id"]),"")
        if nm not in WANT: continue
        a=agg[nm]; a[0]+=n(x["metrics.impressions"]); a[1]+=n(x["metrics.clicks"])
        a[2]+=n(x["metrics.cost_micros"])/1e6; a[3]+=n(x["metrics.conversions"])
    print(f"  {'country':18}{'impr':>8}{'clicks':>8}{'cost HK$':>10}{'conv':>6}{'CPC':>8}{'CPA':>10}")
    for nm,a in sorted(agg.items(),key=lambda z:-z[1][2]):
        cpa=f"{a[2]/a[3]:,.0f}" if a[3] else "-"
        print(f"  {nm:18}{a[0]:>8.0f}{a[1]:>8.0f}{a[2]:>10,.0f}{a[3]:>6.1f}"
              f"{a[2]/max(a[1],1):>8.1f}{cpa:>10}")
    print("\n=== CONVERSIONS RECORDED IN THESE MARKETS, BY CAMPAIGN ===")
    for x in sorted(await c.search("SELECT campaign.name, user_location_view.country_criterion_id, "
      f"metrics.conversions, metrics.cost_micros FROM user_location_view WHERE {D}"),
      key=lambda z:-n(z["metrics.conversions"])):
        nm=geo.get(str(x["user_location_view.country_criterion_id"]),"")
        if nm in WANT and n(x["metrics.conversions"])>0:
            print(f"  {nm:16} {x['campaign.name'][:34]:36} conv={n(x['metrics.conversions']):>5.1f} "
                  f"cost=HK${n(x['metrics.cost_micros'])/1e6:>8,.0f}")
asyncio.run(m())
