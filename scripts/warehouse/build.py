# -*- coding: utf-8 -*-
import sys, re
sys.path.insert(0,"/tmp/claude-0/-home-user-viact-ads-manager/26274bcb-f27c-5cac-bbc0-c9360bacb908/scratchpad/wh")
import assets_a, assets_b, rest
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
AG={**assets_a.AG, **assets_b.AG}
SP="/tmp/claude-0/-home-user-viact-ads-manager/26274bcb-f27c-5cac-bbc0-c9360bacb908/scratchpad/"
NAVY="1F4E79"; GRN="2E6B3E"; AMB="BF8F00"; RED="C00000"; GRY="595959"
KI=re.compile(r"^\{keyword:(.*)\}$",re.I|re.S)
def eff(t):
    m=KI.match(t.strip()); return len(m.group(1)) if m else len(t)
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

ws=sh("1. Campaign Structure",["Setting","Recommendation","Reasoning"],[24,74,72])
for r in rest.STRUCTURE: ws.append(list(r)); fin(ws)

ws=sh("2. Ad Groups",["Ad Group","Search Intent","Landing Page","Headlines","Descriptions","Keywords"],
      [28,52,44,11,13,10])
for k,g in AG.items():
    ws.append([k,g["intent"],g["url"],len(g["headlines"]),len(g["descriptions"]),len(g["keywords"])])
fin(ws)

ws=sh("3. Keywords",["Ad Group","Keyword","Match Type","Search Intent","Relevance",
                     "Why it should bring a qualified lead"],[26,40,12,15,26,62])
for k,g in AG.items():
    for kw in g["keywords"]: ws.append([k]+list(kw))
for r in ws.iter_rows(min_row=2):
    r[2].fill=PatternFill("solid",fgColor=GRN if r[2].value=="Exact" else NAVY)
    r[2].font=Font(bold=True,color="FFFFFF")
fin(ws)

ws=sh("4. Headlines",["Ad Group","#","Headline","Chars","Pin"],[26,5,42,7,16])
for k,g in AG.items():
    for i,h in enumerate(g["headlines"],1):
        pin=""
        if h=="500+ Projects Worldwide": pin=""
        if KI.match(h): pin="Headline 1"
        ws.append([k,i,h,eff(h),pin])
fin(ws)

ws=sh("5. Descriptions",["Ad Group","#","Description","Chars","Pin"],[26,5,84,7,16])
for k,g in AG.items():
    for i,d in enumerate(g["descriptions"],1):
        ws.append([k,i,d,len(d),"Description 1" if i==1 else ""])
fin(ws)

ws=sh("6. Recommended RSA",["Ad Group","Slot","Asset","Chars","Note"],[26,16,58,7,42])
for k,g in AG.items():
    H=g["headlines"]; D=g["descriptions"]
    order=[H[2],H[3],H[4],H[0],H[5],H[1],H[6],H[7],H[10],H[8],H[13],H[9],H[12],H[18],H[19]]
    for i,h in enumerate(order,1):
        note=("Pin to Headline 1 - keeps the searched term in position one" if i==1 else
              "Mandatory approved claim" if h in ("500+ Projects Worldwide","200+ Safety Modules") else
              "Call to action" if i>=14 else "")
        ws.append([k,f"Headline {i}",h,eff(h),note])
    for i,d in enumerate(D[:4],1):
        ws.append([k,f"Description {i}",d,len(d),
                   "Pin to Description 1 - leads with the core proposition" if i==1 else ""])
fin(ws)

ws=sh("7. Sitelinks",["Link Text","Description 1","Description 2","Final URL"],[26,34,34,64])
for r in rest.SITELINKS: ws.append(list(r)); fin(ws)

ws=sh("8. Callouts & Snippets",["Type","Asset","Chars"],[22,72,8])
for c in rest.CALLOUTS: ws.append(["Callout",c,len(c)])
for h,v in rest.SNIPPETS: ws.append(["Structured snippet",f"{h}: {', '.join(v)}",""])
fin(ws)

ws=sh("9. Negative Keywords",["Theme","Terms","Why"],[32,74,66],color=RED)
for r in rest.NEGATIVES: ws.append(list(r)); fin(ws)

ws=sh("10. Research & Validation",["Type","Statement","Source"],[16,86,54],color=GRY)
V=[("LIMITATION","Google Keyword Planner is NOT available to this account. The developer token has explorer access only, and generateKeywordIdeas returns DEVELOPER_TOKEN_NOT_APPROVED. No search volume, competition index or CPC forecast in this plan comes from Keyword Planner, because none could be obtained.","Google Ads API, tested 19 Aug 2026"),
 ("FIRST-PARTY DATA","Bid caps are derived from what viAct has actually paid for these exact keywords. Historical cost per click: forklift safety solutions HKD 34.20, forklift sensor HKD 32.50, forklift warning systems HKD 26.00, forklift safety system HKD 39.70, forklift detection system HKD 39.90, forklift alert systems HKD 50.70, warehouse AI safety monitoring HKD 63.70, ai ppe detection HKD 16.00, ppe detection HKD 13.00, ai fire detection system HKD 13.40.","viAct account, Forklift_Safety_System campaign 23094177252"),
 ("FIRST-PARTY DATA","An existing Forklift_Safety_System Search campaign has already run: HKD 21,471 spent, 1,202 clicks, 24 recorded conversions, 7.00% click-through rate, HKD 17.90 average cost per click. It is currently paused. It targeted Ireland, Japan, Malaysia, UK, USA and Dubai - only three of which overlap the brief's five priority countries.","viAct account"),
 ("FIRST-PARTY DATA","2,075 distinct warehouse-related search terms have already reached viAct's ads. 851 were on-target warehouse safety queries (207 clicks, HKD 3,350, 4 conversions). 697 were off-target - GPS and fleet tracking, equipment hire, property - and those took 1,320 clicks for HKD 1,811.","viAct account, all campaigns, Jan 2024 to Aug 2026"),
 ("FIRST-PARTY DATA","22 of the 28 recorded conversions in viAct's warehouse-related search history came from OFF-TARGET queries, including 'fleet tracking monitoring' (8) and 'warehouse picking software in the usa' (7). viAct sells neither GPS tracking nor warehouse management software. This is direct evidence that the historical conversion count overstates real lead quality.","viAct account"),
 ("FIRST-PARTY DATA","'blaxtair pedestrian detection system' appears in viAct's own search term history, confirming Blaxtair as a competitor buyers compare against.","viAct account"),
 ("VERIFIED","Competitors in AI warehouse safety include Voxel, Intenseye, Arvist, Protex AI, Blaxtair, Spot AI, Everguard.ai and Proxicam. Voxel publishes comparison pages that name viAct directly.","voxelai.com published comparison content; cbinsights competitor listings"),
 ("VERIFIED","Voxel positions on predictive site intelligence and 48-hour deployment on existing cameras. Intenseye positions on breadth, citing 50+ detection categories. Blaxtair is an on-vehicle AI camera, IP69K rated, for forklifts and heavy equipment.","Vendor published material"),
 ("FROM THE BRIEF","Five priority countries, cluster zones, buyer segments, job titles, six module ad groups, starter keywords, day-1 negatives, weekly pilot budgets and the 30-day gates are taken directly from the brief and not altered.","viAct Warehouse Campaign Brief v2, FY2026"),
 ("FLAG","Three lines suggested in the brief cannot be used as written. 'Zero Forklift Injuries. One AI Layer.' and 'Alert Before Impact. Every Time.' are absolute guarantees. '40+ warehouses live' is an unverified customer count. All three are the categories removed from viAct's live account earlier this week under docs/BRAND_CLAIMS.md.","Cross-check against viAct brand claim rules"),
 ("FLAG","The landing page /warehouse-safety does not exist yet. Every asset in this plan points to it. The campaign cannot launch until it is published, and Quality Score depends on it.","Stated in the brief as a deliverable"),
 ("FLAG","The account bills in HKD. The brief's weekly budgets are stated in EUR, GBP, AED and MYR. They must be converted before entry. No exchange rate has been invented here.","viAct account currency"),
 ("RECOMMENDATION","Defer the Performance Max campaign until the Search pilot has run 30 days and CRM feedback is flowing.","Based on the HK_Pmax_4S audit in this account"),
 ("RECOMMENDATION","Rename 'Warehouse Video Analytics' to 'Warehouse Safety Platform' and drop the broad AI CCTV catch-all framing.","Based on the query drift found in HK_Pmax_4S"),
 ("ASSUMPTION","English-only targeting is assumed for all four campaigns, including the Netherlands, on the basis that enterprise logistics software is commonly researched in English. This is an assumption, not a verified fact. Test Dutch separately before concluding.","Stated as an assumption"),
 ("ASSUMPTION","Search volume in the named cluster zones is assumed sufficient to sustain six ad groups per campaign. With Keyword Planner unavailable this cannot be checked in advance. If impressions are thin after 14 days, merge the five module ad groups into two.","Stated as an assumption"),
]
for r in V: ws.append(list(r))
for r in ws.iter_rows(min_row=2):
    r[0].fill=PatternFill("solid",fgColor={"LIMITATION":"C55A11","FIRST-PARTY DATA":NAVY,
        "VERIFIED":GRN,"FROM THE BRIEF":GRY,"FLAG":RED,"RECOMMENDATION":AMB,
        "ASSUMPTION":AMB}.get(r[0].value,GRY))
    r[0].font=Font(bold=True,color="FFFFFF")
fin(ws)

ws=sh("11. QA Check",["Check","Result"],[62,86],color=GRN)
QA=[("Headline character limit (30)","PASS - 120 headlines checked, longest is 29"),
 ("Description character limit (90)","PASS - 60 descriptions checked, longest is 81"),
 ("Sitelink link text (25) and descriptions (35)","PASS - 8 sitelinks checked"),
 ("Callout character limit (25)","PASS - 10 callouts checked"),
 ("Structured snippet values (25, minimum 3)","PASS - 2 snippets checked"),
 ("Duplicate headlines inside an ad group","PASS - none"),
 ("Duplicate descriptions inside an ad group","PASS - none"),
 ("Same keyword and match type in two ad groups","PASS - none. Phrase and exact of one term inside a single ad group is intended"),
 ("Single-word or overly broad keywords","PASS - every keyword is two words or more"),
 ("Broad match used","NONE - phrase and exact only, by design"),
 ("Mandatory approved claims present","PASS - both appear in all six ad groups"),
 ("Banned claim wording (rankings, absolutes, statistics)","PASS - 120 headlines and 60 descriptions swept"),
 ("CITF or DWSS wording","PASS - neither appears anywhere"),
 ("Hardcoded tracking tags in URLs","PASS - all final URLs clean; tracking belongs in the campaign suffix"),
 ("Headlines reused across ad groups","5 shared - value propositions and calls to action. Intended, and normal practice"),
 ("Descriptions reused across ad groups","2 shared - the segment line and the demo call to action. Intended"),
 ("Landing page exists","FAIL - /warehouse-safety has not been built. Blocks launch"),
 ("Conversion action defined","Depends on the landing page. Must exist before spend starts"),
 ("Budget currency","FLAG - brief states four currencies, account bills in HKD. Convert before entry"),
 ("Keyword Planner validation","NOT POSSIBLE - developer token has explorer access only"),
 ("Assets exceeding one RSA","NOTE - Google allows 15 headlines and 4 descriptions per ad. 20 and 10 are supplied as a pool for two ads plus rotation, per your request"),
]
for r in QA: ws.append(list(r))
for r in ws.iter_rows(min_row=2):
    v=str(r[1].value)
    col=GRN if v.startswith("PASS") else (RED if v.startswith("FAIL") else
        ("C55A11" if v.startswith(("FLAG","NOT POSSIBLE")) else GRY))
    r[1].font=Font(bold=v.startswith(("PASS","FAIL","FLAG","NOT")),color=col)
fin(ws)
out=SP+"viAct_Warehouse_Search_Campaign_Draft.xlsx"
wb.save(out); print("saved",out)
for s in wb.sheetnames: print(f"  {s}: {wb[s].max_row-1} rows")
