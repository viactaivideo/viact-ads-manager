# -*- coding: utf-8 -*-
"""Sweep every enabled Performance Max text asset on active campaigns.

Two earlier batches of PMax removals partially failed without raising, so this
re-checks from live state rather than trusting the earlier mutate results.
"""
import asyncio, sys, re, collections
from viact_ads.client import GoogleAdsClient
from viact_ads.config import load_config
CID="3767588103"; APPLY="--apply" in sys.argv
R=lambda s,*i: f"customers/{CID}/{s}/" + "~".join(str(x) for x in i)
BAN=[(re.compile(r"lowest price|guarantee",re.I),"price guarantee we cannot stand behind"),
     (re.compile(r"\bno\.?\s?1\b|#1|\bbest\b|\bleading\b|\btop\b|\bmost \w+|world'?s",re.I),"ranking claim"),
     (re.compile(r"\d+\s?%|\b\d+x\b",re.I),"performance figure with no source"),
     (re.compile(r"zero blind|zero accident",re.I),"absolute claim"),
     (re.compile(r"\bdwss\b|works supervision",re.I),"DWSS - product not supported")]
MIN={"HEADLINE":3,"LONG_HEADLINE":1,"DESCRIPTION":2}
async def m():
    c=GoogleAdsClient(load_config())
    rows=await c.search("SELECT campaign.name, campaign.status, asset_group.id, asset_group.name, "
      "asset_group.status, asset_group_asset.field_type, asset_group_asset.status, asset.id, "
      "asset.text_asset.text FROM asset_group_asset WHERE campaign.status='ENABLED' "
      "AND asset_group.status='ENABLED' AND asset_group_asset.status='ENABLED'")
    cnt=collections.Counter((x["asset_group.id"],x["asset_group_asset.field_type"]) for x in rows)
    drop=[]
    for x in rows:
        t=x.get("asset.text_asset.text")
        if not t: continue
        for rx,why in BAN:
            if rx.search(t):
                drop.append((x,why)); break
    print(f"{len(rows)} enabled PMax text assets on active campaigns | {len(drop)} carry a banned claim\n")
    after=dict(cnt)
    ops=[]
    for x,why in drop:
        k=(x["asset_group.id"],x["asset_group_asset.field_type"])
        ft=x["asset_group_asset.field_type"]
        if ft in MIN and after[k]-1 < MIN[ft]:
            print(f"  SKIP (would drop {ft} below Google's minimum): {x['asset.text_asset.text']}")
            continue
        after[k]-=1
        ops.append({"remove":R("assetGroupAssets",x["asset_group.id"],x["asset.id"],ft)})
        print(f"  REMOVE {x['campaign.name']:14} {ft:14} {x['asset.id']:>13}  [{why}]")
        print(f"         {x['asset.text_asset.text']}")
    if not ops: print("  nothing to remove"); return
    r=await c.mutate("asset_group_asset",ops,validate_only=not APPLY)
    print(f"\n{'APPLIED' if APPLY else 'VALIDATED'} {len(r.get('results',[]))} of {len(ops)}")
    if APPLY:
        chk=await c.search("SELECT campaign.name, asset_group.id, asset_group_asset.field_type, "
          "asset_group_asset.status, asset.id, asset.text_asset.text FROM asset_group_asset "
          "WHERE campaign.status='ENABLED' AND asset_group.status='ENABLED' "
          "AND asset_group_asset.status='ENABLED'")
        left=[x for x in chk if x.get("asset.text_asset.text")
              and any(rx.search(x["asset.text_asset.text"]) for rx,_ in BAN)]
        print(f"re-check from live state: {len(left)} banned claims remaining")
        for x in left: print("   still there:",x["asset.id"],x["asset.text_asset.text"])
asyncio.run(m())
