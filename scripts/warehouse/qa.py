# -*- coding: utf-8 -*-
"""QA every asset before it is presented."""
import re, sys, collections
sys.path.insert(0,"/tmp/claude-0/-home-user-viact-ads-manager/26274bcb-f27c-5cac-bbc0-c9360bacb908/scratchpad/wh")
import assets_a, assets_b
AG={**assets_a.AG, **assets_b.AG}
KI=re.compile(r"^\{keyword:(.*)\}$",re.I|re.S)
def eff(t):
    m=KI.match(t.strip()); return len(m.group(1)) if m else len(t)
BAN=re.compile(r"\bno\.?\s?1\b|#1|\bbest\b|\bleading\b|\btop\b|\bmost \w+|world'?s|"
               r"\bguarantee\b|\bzero\b|\bevery time\b|100\s?%|\d+\s?%|\b\d+x\b|"
               r"\bawarded\b|\bcheapest\b|\bonly\b(?! )|\bcitf\b|\bdwss\b",re.I)
OK={"500+ Projects Worldwide","200+ Safety Modules"}
fail=[]; warn=[]
allh=collections.Counter(); alld=collections.Counter(); allk=collections.Counter()
for name,g in AG.items():
    H=g["headlines"]; D=g["descriptions"]; K=g["keywords"]
    if len(H)!=20: fail.append(f"{name}: {len(H)} headlines, expected 20")
    if len(D)!=10: fail.append(f"{name}: {len(D)} descriptions, expected 10")
    for t in H:
        if eff(t)>30: fail.append(f"{name}: headline {t!r} = {eff(t)} chars (max 30)")
        if t not in OK and BAN.search(t): fail.append(f"{name}: BANNED wording in headline {t!r}")
        allh[t]+=1
    for t in D:
        if len(t)>90: fail.append(f"{name}: description {t!r} = {len(t)} chars (max 90)")
        if BAN.search(t) and not any(o in t for o in OK):
            fail.append(f"{name}: BANNED wording in description {t!r}")
        alld[t]+=1
    if len(set(H))!=len(H):
        d=[x for x in set(H) if H.count(x)>1]; fail.append(f"{name}: duplicate headline in same ad group {d}")
    if len(set(D))!=len(D):
        d=[x for x in set(D) if D.count(x)>1]; fail.append(f"{name}: duplicate description {d}")
    for x in OK:
        if x not in H: fail.append(f"{name}: missing mandatory headline {x!r}")
    kt=[(k[0],k[1]) for k in K]
    # phrase and exact of the same term inside one ad group is standard practice,
    # so uniqueness is checked on the term AND match type together
    for k in kt: allk[k]+=1
    if len(set(kt))!=len(kt): fail.append(f"{name}: same keyword and match type twice in one ad group")
    for k in K:
        if len(k)!=5: fail.append(f"{name}: keyword row {k[0]} missing a column")
        if k[1] not in ("Phrase","Exact"): fail.append(f"{name}: bad match type {k[1]}")
        if k[1]=="Exact" and not (k[0].startswith("[") and k[0].endswith("]")):
            fail.append(f"{name}: exact keyword not bracketed: {k[0]}")
        if k[1]=="Phrase" and k[0].startswith("["):
            fail.append(f"{name}: phrase keyword bracketed: {k[0]}")
        if len(k[0].strip("[]").split())<2:
            warn.append(f"{name}: single-word keyword {k[0]!r} - too broad")
dups=[k for k,v in allk.items() if v>1]
if dups: fail.append(f"same keyword+match type in more than one ad group: {dups}")
xh=[h for h,v in allh.items() if v>1 and h not in OK and not KI.match(h)]
for h in xh: warn.append(f"headline reused across ad groups: {h!r} ({allh[h]}x)")
xd=[d for d,v in alld.items() if v>1]
for d in xd: warn.append(f"description reused across ad groups: {d[:52]!r} ({alld[d]}x)")
print("="*72)
print(f"AD GROUPS: {len(AG)}")
tot_h=sum(len(g['headlines']) for g in AG.values())
tot_d=sum(len(g['descriptions']) for g in AG.values())
tot_k=sum(len(g['keywords']) for g in AG.values())
print(f"HEADLINES: {tot_h}   DESCRIPTIONS: {tot_d}   KEYWORDS: {tot_k}")
print("="*72)
print(f"\nFAILURES: {len(fail)}")
for f in fail: print("  X",f)
print(f"\nWARNINGS: {len(warn)}")
for w in warn: print("  !",w)
if not fail:
    print("\nAll character limits, mandatory headlines, duplicate and banned-wording checks passed.")
    print("\nLongest headline per ad group:")
    for name,g in AG.items():
        m=max(g["headlines"],key=eff); print(f"  {name[:30]:32} {eff(m):>2} chars  {m}")
    print("\nLongest description per ad group:")
    for name,g in AG.items():
        m=max(g["descriptions"],key=len); print(f"  {name[:30]:32} {len(m):>2} chars  {m[:56]}")
