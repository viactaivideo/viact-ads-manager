import asyncio, json
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config
C="23029018962"; D="segments.date BETWEEN '2025-09-19' AND '2026-08-18'"
async def m():
    c=GoogleAdsClient(load_config())
    print("=== WHERE USERS ACTUALLY WERE (physical location) ===")
    geo={}
    for x in await c.search("SELECT geo_target_constant.id, geo_target_constant.name "
      "FROM geo_target_constant WHERE geo_target_constant.target_type='Country'"):
        geo[str(x["geo_target_constant.id"])]=x["geo_target_constant.name"]
    for x in await c.search("SELECT campaign.id, user_location_view.country_criterion_id, "
      "metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, "
      f"metrics.all_conversions FROM user_location_view WHERE campaign.id={C} AND {D}"):
        cid=str(x["user_location_view.country_criterion_id"])
        print(f"  {geo.get(cid,cid):22} impr={float(x['metrics.impressions']):>8.0f} "
              f"clicks={float(x['metrics.clicks']):>6.0f} cost={float(x['metrics.cost_micros'])/1e6:>8,.0f} "
              f"conv={float(x['metrics.conversions']):>5.1f} allConv={float(x['metrics.all_conversions']):>7.1f}")
    print("\n=== USER LISTS INSIDE THE AUDIENCE SIGNALS ===")
    ids=["6616668118","7068182066","7307197850","7308282796","7973705478","7973705568",
         "8099772717","8805618565"]
    for x in await c.search("SELECT user_list.id, user_list.name, user_list.type, "
      "user_list.size_for_display, user_list.size_for_search, user_list.membership_status "
      f"FROM user_list WHERE user_list.id IN ({','.join(ids)})"):
        print(f"  {x['user_list.id']:>12} {str(x['user_list.name'])[:44]:46} {x['user_list.type']:22} "
              f"display={x.get('user_list.size_for_display')} search={x.get('user_list.size_for_search')}")
    print("\n=== INTEREST CATEGORIES IN THE SIGNALS ===")
    aud=await c.search("SELECT audience.id, audience.name, audience.dimensions FROM audience "
                       "WHERE audience.id IN (136817198,325232746)")
    uids=set()
    for a in aud:
        for dim in a.get("audience.dimensions") or []:
            for seg in (dim.get("audienceSegments") or {}).get("segments",[]):
                u=(seg.get("userInterest") or {}).get("userInterestCategory")
                if u: uids.add(u.rsplit("/",1)[-1])
    print(f"  {len(uids)} interest categories referenced")
    if uids:
        for x in await c.search("SELECT user_interest.user_interest_id, user_interest.name, "
          f"user_interest.taxonomy_type FROM user_interest WHERE user_interest.user_interest_id "
          f"IN ({','.join(sorted(uids))})"):
            print(f"    {x['user_interest.user_interest_id']:>8} {x['user_interest.taxonomy_type']:22} "
                  f"{x['user_interest.name']}")
    print("\n=== PLACEMENT EXCLUSION LISTS ATTACHED AT ACCOUNT LEVEL ===")
    try:
        r=await c.search("SELECT shared_set.id, shared_set.name, shared_set.type "
                         "FROM shared_set WHERE shared_set.type='NEGATIVE_PLACEMENTS'")
        for x in r: print(f"  list exists: {x['shared_set.name']}")
        r2=await c.search("SELECT customer_negative_criterion.id, customer_negative_criterion.type, "
          "customer_negative_criterion.placement.url, customer_negative_criterion.mobile_application.name, "
          "customer_negative_criterion.youtube_channel.channel_id FROM customer_negative_criterion")
        print(f"  account-level negative criteria in place: {len(r2)}")
        import collections
        for t,n in collections.Counter(x["customer_negative_criterion.type"] for x in r2).items():
            print(f"     {t}: {n}")
    except Exception as e: print("  ",str(e)[:200])
asyncio.run(m())
