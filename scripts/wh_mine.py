# -*- coding: utf-8 -*-
"""Mine the account's own history for warehouse / forklift / logistics demand."""
import asyncio, json, re, collections
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config
SP="/tmp/claude-0/-home-user-viact-ads-manager/26274bcb-f27c-5cac-bbc0-c9360bacb908/scratchpad/"
def n(v):
    try: return float(v)
    except: return 0.0
async def m():
    c=GoogleAdsClient(load_config())
    print("=== FORKLIFT_SAFETY_SYSTEM CAMPAIGN: lifetime ===")
    for x in await c.search("SELECT campaign.id, campaign.name, campaign.status, "
      "campaign.start_date_time, campaign.advertising_channel_type, campaign_budget.amount_micros "
      "FROM campaign WHERE campaign.name LIKE '%Forklift%'"):
        print(f"  {x['campaign.name']} id={x['campaign.id']} {x['campaign.status']} "
              f"{x['campaign.advertising_channel_type']} started {x.get('campaign.start_date_time')} "
              f"budget={n(x['campaign_budget.amount_micros'])/1e6:.0f}/day")
    cid=None
    for x in await c.search("SELECT campaign.id, campaign.name FROM campaign WHERE campaign.name LIKE '%Forklift%'"):
        cid=x["campaign.id"]
    if cid:
        r=await c.search("SELECT campaign.id, metrics.impressions, metrics.clicks, metrics.cost_micros, "
          f"metrics.conversions, metrics.ctr, metrics.average_cpc FROM campaign WHERE campaign.id={cid} "
          "AND segments.date BETWEEN '2024-01-01' AND '2026-08-18'")
        for x in r:
            print(f"  lifetime: impr={n(x['metrics.impressions']):.0f} clicks={n(x['metrics.clicks']):.0f} "
                  f"cost=HK${n(x['metrics.cost_micros'])/1e6:,.0f} conv={n(x['metrics.conversions']):.1f} "
                  f"CTR={n(x['metrics.ctr'])*100:.2f}% CPC=HK${n(x['metrics.average_cpc']):.1f}")
        print("\n  --- ad groups ---")
        for x in sorted(await c.search("SELECT campaign.id, ad_group.name, ad_group.status, "
          "metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions "
          f"FROM ad_group WHERE campaign.id={cid} AND segments.date BETWEEN '2024-01-01' AND '2026-08-18'"),
          key=lambda z:-n(z["metrics.cost_micros"])):
            print(f"    {x['ad_group.status']:8} {x['ad_group.name'][:30]:32} "
                  f"cost=HK${n(x['metrics.cost_micros'])/1e6:>7,.0f} clicks={n(x['metrics.clicks']):>5.0f} "
                  f"conv={n(x['metrics.conversions']):>4.1f}")
    print("\n=== ACCOUNT-WIDE SEARCH TERMS MATCHING WAREHOUSE / FORKLIFT / LOGISTICS ===")
    RX=re.compile(r"forklift|warehouse|pallet|loading (dock|bay)|dock|3pl|logistic|"
                  r"cold storage|distribution cent|reversing|pedestrian|racking|"
                  r"material handling|agv|reach truck|hi.?vis",re.I)
    agg=collections.defaultdict(lambda:[0,0,0.0,0.0,set()])
    for x in await c.search("SELECT campaign.name, search_term_view.search_term, "
      "metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions "
      "FROM search_term_view WHERE segments.date BETWEEN '2024-01-01' AND '2026-08-18'"):
        t=x["search_term_view.search_term"]
        if not RX.search(t): continue
        a=agg[t]; a[0]+=n(x["metrics.impressions"]); a[1]+=n(x["metrics.clicks"])
        a[2]+=n(x["metrics.cost_micros"])/1e6; a[3]+=n(x["metrics.conversions"])
        a[4].add(x["campaign.name"])
    print(f"  {len(agg)} distinct warehouse-related search terms have reached viAct's ads\n")
    print(f"  {'search term':52}{'impr':>7}{'clk':>5}{'cost':>8}{'cnv':>5}")
    for t,v in sorted(agg.items(),key=lambda z:(-z[1][1],-z[1][0]))[:70]:
        print(f"  {t[:51]:52}{v[0]:>7.0f}{v[1]:>5.0f}{v[2]:>8,.0f}{v[3]:>5.1f}")
    json.dump({k:[v[0],v[1],v[2],v[3],sorted(v[4])] for k,v in agg.items()},
              open(SP+"wh_terms.json","w"),indent=0)
asyncio.run(m())
