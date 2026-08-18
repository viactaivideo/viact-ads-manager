"""Classify every text asset on active Search/PMax campaigns against BRAND_CLAIMS.md."""
import json, re, collections
SP="/tmp/claude-0/-home-user-viact-ads-manager/26274bcb-f27c-5cac-bbc0-c9360bacb908/scratchpad/"
d=json.load(open(SP+"all_assets.json"))
SCOPE={"GCC_Search_Leads","SG_Search_Leads","HK_Search_Leads",
       "GCC_Pmax_4S","HK_Pmax_4S","SG_Pmax_VSS"}

RULES=[
 ("STAT",      re.compile(r"\b\d{1,3}\s?%|\b\d+x\b", re.I)),
 ("SUPERIOR",  re.compile(r"\bno\.?\s?1\b|#1|\bbest\b|\btop\b|\bleading\b|\bmost\s+\w+|world'?s?\b|\bworld\s+leading\b|\b1st\b", re.I)),
 ("ABSOLUTE",  re.compile(r"\bzero\b|\bguarantee\b|\b100\s?%|\ball\b(?=\s+accidents)", re.I)),
 ("AWARD",     re.compile(r"\bawarded\b|\bfortune 500\b|\baward\b", re.I)),
 ("ENDORSE",   re.compile(r"\bMOM[-\s]?Approved\b|\bapproved by\b|\bcertified by\b", re.I)),
 ("UNVERIFIED-COUNT", re.compile(r"\btrusted (?:by|in|on|across)\b|\b\d+\+ (?:countries|years|singapore projects|sg contractors)\b|\b\d+\+ years\b", re.I)),
]
# numeric claims that must match canon
PROJ=re.compile(r"(\d+)\+?\s+(?:successful\s+|global\s+)?projects", re.I)
MOD =re.compile(r"(\d+)\+?\s+(?:ai\s+|smart\s+|safety\s+|pre-built\s+|in-built\s+)*(?:safety\s+)?(?:modules|rules)", re.I)

def flags(t):
    if not t: return []
    out=[]
    for name,rx in RULES:
        if rx.search(t): out.append(name)
    m=PROJ.search(t)
    if m and m.group(1)!="500": out.append(f"PROJ≠500 ({m.group(0)})")
    elif m and "500+ Projects Worldwide" not in t: out.append(f"PROJ-WORDING ({m.group(0)})")
    m=MOD.search(t)
    if m and m.group(1)!="200": out.append(f"MOD≠200 ({m.group(0)})")
    elif m and "200+ Safety Modules" not in t: out.append(f"MOD-WORDING ({m.group(0)})")
    return out

rows=[]
def add(camp, loc, kind, aid, text):
    f=flags(text)
    if f: rows.append((camp, loc, kind, str(aid), text, ",".join(f)))

for a in d["rsa"]:
    c=a["campaign.name"]
    if c not in SCOPE: continue
    loc=f"{a['ad_group.name']} / ad {a['ad_group_ad.ad.id']}"
    for h in a.get("ad_group_ad.ad.responsive_search_ad.headlines") or []:
        add(c,loc,"HEADLINE","-",h.get("text"))
    for x in a.get("ad_group_ad.ad.responsive_search_ad.descriptions") or []:
        add(c,loc,"DESCRIPTION","-",x.get("text"))

for a in d["ag_assets"]:
    c=a["campaign.name"]
    if c not in SCOPE: continue
    add(c,f"asset group {a['asset_group.id']}",a["asset_group_asset.field_type"],
        a["asset.id"],a.get("asset.text_asset.text"))

def etext(a):
    t=a["asset.type"]
    if t=="SITELINK":
        return " | ".join(filter(None,[a.get("asset.sitelink_asset.link_text"),
            a.get("asset.sitelink_asset.description1"),a.get("asset.sitelink_asset.description2")]))
    if t=="CALLOUT": return a.get("asset.callout_asset.callout_text")
    if t=="STRUCTURED_SNIPPET":
        v=a.get("asset.structured_snippet_asset.values") or []
        return f"{a.get('asset.structured_snippet_asset.header')}: {', '.join(v)}"
    return None

for res,lab in (("customer_asset","ACCOUNT"),("campaign_asset","CAMPAIGN"),("ad_group_asset","AD GROUP")):
    for a in d[res]:
        if a.get(f"{res}.status")!="ENABLED": continue
        c=a.get("campaign.name","(account-level)")
        if lab!="ACCOUNT" and c not in SCOPE: continue
        loc=lab if lab!="AD GROUP" else f"AD GROUP {a.get('ad_group.name')}"
        add(c,loc,a["asset.type"],a["asset.id"],etext(a))

seen=set(); uniq=[]
for r in rows:
    k=(r[0],r[1],r[3],r[4])
    if k in seen: continue
    seen.add(k); uniq.append(r)

print(f"{len(uniq)} flagged instances\n")
by=collections.defaultdict(list)
for r in uniq: by[r[0]].append(r)
for c in sorted(by):
    print("="*78); print(c)
    for camp,loc,kind,aid,text,f in sorted(by[c],key=lambda x:(x[1],x[2])):
        print(f"  [{f}]")
        print(f"    {kind} {aid} @ {loc}")
        print(f"    {text}")
json.dump([dict(zip(("campaign","location","kind","asset_id","text","flags"),r)) for r in uniq],
          open(SP+"flagged.json","w"), indent=1)
