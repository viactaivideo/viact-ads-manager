# -*- coding: utf-8 -*-
"""Remove two SG_Pmax_VSS assets whose earlier removal did not take effect."""
import asyncio, sys, collections
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config
CID="3767588103"; AG="6616994854"; APPLY="--apply" in sys.argv
R=lambda s,*i: f"customers/{CID}/{s}/" + "~".join(str(x) for x in i)
DROP=[("124768005549","HEADLINE","No.1 Construction Surveillance"),
      ("131808933047","DESCRIPTION","Best Construction Safety App in Singapore: 90% Less Accidents...")]
async def m():
    c=GoogleAdsClient(load_config())
    rows=await c.search("SELECT campaign.name, asset_group.id, asset_group.status, "
      "asset_group_asset.field_type, asset_group_asset.status, asset.id "
      f"FROM asset_group_asset WHERE asset_group.id={AG} AND asset_group_asset.status='ENABLED'")
    n=collections.Counter(x["asset_group_asset.field_type"] for x in rows)
    print("current counts:",{k:v for k,v in n.items() if k in ("HEADLINE","LONG_HEADLINE","DESCRIPTION")})
    after=dict(n)
    for _,ft,_ in DROP: after[ft]=after.get(ft,0)-1
    print("after removal :",{k:v for k,v in after.items() if k in ("HEADLINE","LONG_HEADLINE","DESCRIPTION")})
    MIN={"HEADLINE":3,"LONG_HEADLINE":1,"DESCRIPTION":2}
    for ft,mn in MIN.items():
        if after.get(ft,0)<mn:
            print(f"ABORT: {ft} would fall to {after.get(ft,0)}, below Google's minimum of {mn}"); return
    ops=[{"remove":R("assetGroupAssets",AG,a,ft)} for a,ft,_ in DROP]
    r=await c.mutate("asset_group_asset",ops,validate_only=not APPLY)
    print(f"{'APPLIED' if APPLY else 'VALIDATED'} {len(r.get('results',[]))} of {len(ops)}")
    for a,ft,t in DROP: print(f"  removed {ft:12} {a}  {t}")
asyncio.run(m())
