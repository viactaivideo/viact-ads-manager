# -*- coding: utf-8 -*-
import sys, re
sys.path.insert(0,"/tmp/claude-0/-home-user-viact-ads-manager/26274bcb-f27c-5cac-bbc0-c9360bacb908/scratchpad/wh")
import assets_a, assets_b, rest, v4
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
AG={**assets_a.AG, **assets_b.AG}
SP="/tmp/claude-0/-home-user-viact-ads-manager/26274bcb-f27c-5cac-bbc0-c9360bacb908/scratchpad/"
NAVY="1F4E79"; GRN="2E6B3E"; AMB="BF8F00"; RED="C00000"; GRY="595959"
KI=re.compile(r"^\{keyword:(.*)\}$",re.I|re.S)
def eff(t):
    m=KI.match(t.strip()); return len(m.group(1)) if m else len(t)
CAMPS=["WH_Search_UK","WH_Search_Canada","WH_Search_Australia","WH_Search_Ireland"]
wb=Workbook(); first=True
def sh(name,cols,widths,color=NAVY):
    global first
    ws=wb.active if first else wb.create_sheet(name)
    if first: ws.title=name; first=False
    ws.append(cols)
    for i,_ in enumerate(cols,1):
        c=ws.cell(1,i); c.font=Font(bold=True,color="FFFFFF")
        c.fill=PatternFill("solid",fgColor=color)
        c.alignment=Alignment(horizontal="center",vertical="center",wrap_text=True)
    for i,w in enumerate(widths,1): ws.column_dimensions[chr(64+i)].width=w
    ws.freeze_panes="A2"; return ws
def fin(ws):
    for r in ws.iter_rows(min_row=2):
        for c in r: c.alignment=Alignment(vertical="top",wrap_text=True)

ws=sh("1. Campaign Structure",["Component","Recommendation","Locations / Scope","Reasoning"],[20,54,50,64])
for r in v4.STRUCTURE: ws.append(list(r))
fin(ws)

ws=sh("2. Markets & Evidence",["Market","Tier / Action","viAct's own history","Cost per click","Read"],
      [18,24,40,16,58])
MK=[("United Kingdom","Tier 1 - pilot now","1,804 impressions, 132 clicks, HK$3,316, 0 conversions, 7.32% CTR","HK$25.10",
  "Best-evidenced market. Clicks were earned; nothing converted because there was no warehouse landing page."),
 ("Canada","Tier 1 - pilot now","113 lifetime impressions, ZERO clicks","no data",
  "Never tested. The Tier 1 rank rests on market logic, not on any viAct evidence. Review bids at day 7."),
 ("Australia","Tier 1 - pilot now","33 lifetime impressions, ZERO clicks","no data",
  "Never tested. Same caveat as Canada."),
 ("Ireland","Tier 1 - pilot now","340 impressions, 26 clicks, HK$697, 0 conversions, 7.65% CTR","HK$26.80",
  "Highest click-through of any market tested - but this is Protex AI's home market. See sheet 3."),
 ("United States","Tier 2 - Month 2, narrow","2,392 impressions, 185 clicks, HK$6,033, 6 conversions","HK$32.60",
  "The most expensive market viAct has tested. The brief's caution is supported by viAct's own numbers."),
 ("Belgium","Tier 3 - park","none","-","Brief parks it: small market, EU AI Act, dual language."),
 ("Germany","Tier 3 - skip","9 impressions","-","Brief skips it: EU AI Act high-risk plus works-council veto."),
 ("Italy","Tier 3 - skip","none","-","Brief skips it: EU AI Act, language, slow procurement."),
]
for r in MK: ws.append(list(r))
fin(ws)

ws=sh("3. Competitive Analysis",["Competitor","Presence in your samples","Ad copy observed","Positioning","Note"],
      [16,22,64,58,44])
for r in v4.COMPETITIVE: ws.append(list(r))
fin(ws)

ws=sh("4. Positioning Strategy",["Angle","Verdict","What competitors do","What viAct should do"],[26,34,56,64])
for r in v4.POSITIONING: ws.append(list(r))
for r in ws.iter_rows(min_row=2):
    v=str(r[1].value)
    col=RED if "CANNOT" in v or "HIGHEST DIFFICULTY" in v else (AMB if "GAP" in v or "TABLE STAKES" in v else GRN)
    r[1].fill=PatternFill("solid",fgColor=col); r[1].font=Font(bold=True,color="FFFFFF")
fin(ws)

ws=sh("5. Ad Groups",["Ad Group","Search Intent","Landing Page","Headlines","Descriptions","Keywords"],
      [28,52,42,11,13,10])
for k,g in AG.items():
    ws.append([k,g["intent"],g["url"],len(g["headlines"]),len(g["descriptions"]),len(g["keywords"])])
fin(ws)

ws=sh("6. Keywords",["Ad Group","Keyword","Match Type","Search Intent","Relevance","Why it should bring a qualified lead"],
      [26,40,12,15,26,60])
for k,g in AG.items():
    for kw in g["keywords"]: ws.append([k]+list(kw))
for r in ws.iter_rows(min_row=2):
    r[2].fill=PatternFill("solid",fgColor=GRN if r[2].value=="Exact" else NAVY)
    r[2].font=Font(bold=True,color="FFFFFF")
fin(ws)

ws=sh("7. Headlines",["Ad Group","#","Headline","Chars"],[26,5,44,7])
for k,g in AG.items():
    for i,h in enumerate(g["headlines"],1): ws.append([k,i,h,eff(h)])
fin(ws)

ws=sh("8. Descriptions",["Ad Group","#","Description","Chars"],[26,5,86,7])
for k,g in AG.items():
    for i,d in enumerate(g["descriptions"],1): ws.append([k,i,d,len(d)])
fin(ws)

ws=sh("9. Recommended RSA",["Ad Group","Slot","Asset","Chars","Pin / Note"],[26,15,58,7,44])
for k,g in AG.items():
    H=g["headlines"]; D=g["descriptions"]
    order=[H[2],H[3],H[4],H[0],H[5],H[1],H[6],H[7],H[10],H[8],H[13],H[9],H[12],H[18],H[19]]
    for i,h in enumerate(order,1):
        note=("PIN to Headline 1 - keeps the searched term in position one" if i==1 else
              "Approved claim - mandatory" if h in ("500+ Projects Worldwide","200+ Safety Modules") else
              "Call to action" if i>=14 else "")
        ws.append([k,f"Headline {i}",h,eff(h),note])
    for i,d in enumerate(D[:4],1):
        ws.append([k,f"Description {i}",d,len(d),
                   "PIN to Description 1 - leads with the core proposition" if i==1 else ""])
fin(ws)

ws=sh("10. Sitelinks",["Link Text","Description 1","Description 2","Final URL"],[26,34,34,62])
for r in rest.SITELINKS: ws.append(list(r))
fin(ws)

ws=sh("11. Callouts & Snippets",["Type","Asset","Chars"],[22,74,8])
for c in rest.CALLOUTS: ws.append(["Callout",c,len(c)])
for h,v in rest.SNIPPETS: ws.append(["Structured snippet",f"{h}: {', '.join(v)}",""])
fin(ws)

ws=sh("12. Negative Keywords",["Theme","Terms","Why"],[32,74,64],color=RED)
for r in rest.NEGATIVES: ws.append(list(r))
fin(ws)

ws=sh("13. Research & Validation",["Type","Statement","Source"],[22,84,50],color=GRY)
for r in v4.EVIDENCE: ws.append(list(r))
for r in ws.iter_rows(min_row=2):
    r[0].fill=PatternFill("solid",fgColor={"LIMITATION":"C55A11","FIRST-PARTY DATA":NAVY,
      "VERIFIED FROM YOUR SCREENSHOTS":GRN,"FROM THE BRIEF":GRY,"FLAG":RED,
      "WARNING":RED,"RECOMMENDATION":AMB,"ASSUMPTION":AMB}.get(r[0].value,GRY))
    r[0].font=Font(bold=True,color="FFFFFF")
fin(ws)

ws=sh("14. QA Check",["Check","Result"],[62,88],color=GRN)
QA=[("Headline character limit (30)","PASS - 120 headlines, longest 29"),
 ("Description character limit (90)","PASS - 60 descriptions, longest 81"),
 ("Sitelink text (25) and descriptions (35)","PASS - 8 sitelinks"),
 ("Callout limit (25)","PASS - 10 callouts"),
 ("Structured snippet values (25, min 3)","PASS - 2 snippets"),
 ("Duplicate headlines inside an ad group","PASS - none"),
 ("Duplicate descriptions inside an ad group","PASS - none"),
 ("Same keyword and match type in two ad groups","PASS - none"),
 ("Overly broad or single-word keywords","PASS - all two words or more"),
 ("Broad match used","NONE - phrase and exact only, by design"),
 ("Mandatory approved claims present","PASS - both in all six ad groups"),
 ("Banned wording: rankings, absolutes, statistics","PASS - 180 assets swept"),
 ("Percentage claims copied from competitors","PASS - none. viAct has no substantiated figure"),
 ("Hardcoded tracking tags in URLs","PASS - all clean; tracking belongs in the campaign suffix"),
 ("Recommended RSA fits Google's 15/4 limit","PASS - all six ad groups"),
 ("Country count","FLAG - your message says 9, brief v4 lists 8. Please confirm"),
 ("Landing page exists","FAIL - /warehouse-safety not built. Blocks launch"),
 ("Budget currency","FLAG - five currencies in the brief, account bills in HKD"),
 ("Canada and Australia cost data","FLAG - zero clicks ever. Bid caps are placeholders, not forecasts"),
 ("Privacy positioning","FLAG - competitors lead on privacy; viAct is silent. Needs product confirmation"),
 ("Keyword Planner validation","NOT POSSIBLE - developer token has explorer access only"),
 ("Assets exceeding one RSA","NOTE - 20 headlines and 10 descriptions supplied as a pool; Google allows 15 and 4 per ad"),
]
for r in QA: ws.append(list(r))
for r in ws.iter_rows(min_row=2):
    v=str(r[1].value)
    col=GRN if v.startswith("PASS") else (RED if v.startswith("FAIL") else
        ("C55A11" if v.startswith(("FLAG","NOT POSSIBLE","NONE")) else GRY))
    r[1].font=Font(bold=True,color=col)
fin(ws)
out=SP+"viAct_Warehouse_Campaign_Plan_v4.xlsx"
wb.save(out); print("saved",out)
for s in wb.sheetnames: print(f"  {s}: {wb[s].max_row-1} rows")
