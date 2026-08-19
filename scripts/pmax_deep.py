import asyncio, json
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config
C="23029018962"
async def m():
    c=GoogleAdsClient(load_config())
    print("=== GEO CONSTANTS RESOLVED ===")
    for x in await c.search("SELECT geo_target_constant.id, geo_target_constant.name, "
      "geo_target_constant.canonical_name, geo_target_constant.target_type "
      "FROM geo_target_constant WHERE geo_target_constant.resource_name IN "
      "('geoTargetConstants/2050','geoTargetConstants/2344','geoTargetConstants/2356','geoTargetConstants/2586')"):
        print(f"  {x['geo_target_constant.id']:>6} {x['geo_target_constant.name']:20} "
              f"{x['geo_target_constant.target_type']}")
    print("\n=== AUDIENCE SIGNALS RESOLVED ===")
    for x in await c.search("SELECT audience.id, audience.name, audience.description, "
      "audience.status, audience.dimensions FROM audience WHERE audience.id IN (136817198,325232746)"):
        print(f"  {x['audience.id']} {x['audience.name']}  status={x.get('audience.status')}")
        print(f"    desc: {x.get('audience.description')}")
        print(f"    dimensions: {json.dumps(x.get('audience.dimensions'))[:900]}")
    print("\n=== NEGATIVE KEYWORD LISTS APPLIED TO THIS CAMPAIGN ===")
    r=await c.search("SELECT campaign.id, shared_set.id, shared_set.name, shared_set.type, "
      f"shared_set.status, campaign_shared_set.status FROM campaign_shared_set WHERE campaign.id={C}")
    if not r: print("  NONE - no shared negative keyword list is attached")
    for x in r: print(f"  {x['shared_set.name']} ({x['shared_set.type']}) {x['campaign_shared_set.status']}")
    print("\n=== CAMPAIGN-LEVEL NEGATIVE KEYWORDS ===")
    r=await c.search("SELECT campaign.id, campaign_criterion.keyword.text, "
      f"campaign_criterion.keyword.match_type FROM campaign_criterion WHERE campaign.id={C} "
      "AND campaign_criterion.negative=TRUE AND campaign_criterion.type='KEYWORD'")
    print(f"  {len(r)} negative keywords" if r else "  NONE")
    print("\n=== BRAND EXCLUSION LIST ===")
    r=await c.search("SELECT campaign.id, campaign_criterion.type, campaign_criterion.negative, "
      f"campaign_criterion.brand_list.shared_set FROM campaign_criterion WHERE campaign.id={C} "
      "AND campaign_criterion.type='BRAND_LIST'")
    print(f"  {len(r)} brand lists" if r else "  NONE - no brand exclusions set")
    print("\n=== ACCOUNT-LEVEL NEGATIVE LISTS (would need manual attach to PMax) ===")
    for x in await c.search("SELECT shared_set.id, shared_set.name, shared_set.type, "
      "shared_set.member_count, shared_set.status FROM shared_set WHERE shared_set.status='ENABLED'"):
        print(f"  {x['shared_set.id']} {x['shared_set.name']} ({x['shared_set.type']}) "
              f"members={x.get('shared_set.member_count')}")
    print("\n=== URL EXPANSION / FINAL URL SETTING ===")
    for fld in ("campaign.url_expansion_opt_out",):
        try:
            for x in await c.search(f"SELECT campaign.id, {fld} FROM campaign WHERE campaign.id={C}"):
                print(f"  {fld} = {x.get(fld)}")
        except Exception as e: print(f"  {fld}: not queryable in this API version ({str(e)[:80]})")
asyncio.run(m())
