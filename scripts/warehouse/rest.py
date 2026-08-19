# -*- coding: utf-8 -*-
"""Sitelinks, callouts, snippets, negatives, structure. Limits: link 25, desc 35, callout 25."""
SITELINKS=[
 ("Book A Warehouse Demo","See The AI Run On Your Site","30-Minute Technical Session","https://www.viact.ai/demo"),
 ("Forklift Safety Module","Detect Workers Near Forklifts","Alerts Before Impact","https://www.viact.ai/warehouse-safety"),
 ("PPE Detection Module","Hi-Vis, Helmet And Footwear","Automated Compliance Records","https://www.viact.ai/ppedetection"),
 ("Loading Bay Safety","Monitor Docks And Yard Moves","Flag Unsafe Reversing","https://www.viact.ai/warehouse-safety"),
 ("Fire & Smoke Detection","AI Spots Smoke On Camera","Covers High-Rack Storage","https://www.viact.ai/video-analytics-solution/fire-smoke-wildfire-detection"),
 ("Restricted Zone Alerts","Stop Unauthorised Entry","No Fences Or Turnstiles","https://www.viact.ai/solutions/area-control-safety-system"),
 ("Talk To Our Sales Team","Discuss Scope And Rollout","Speak With A Specialist","https://www.viact.ai/contactsales"),
 ("Multi-Site Dashboard","One View Across Every Site","Access Anytime, Anywhere","https://www.viact.ai/vihub"),
]
CALLOUTS=["Works With Existing CCTV","Multi-Site Deployment","500+ Projects Worldwide",
 "200+ Safety Modules","Built For 3PL Operators","Retrofit, No New Cameras",
 "Audit-Ready Records","Real-Time Safety Alerts","Cold Storage Ready","Central HSE Dashboard"]
SNIPPETS=[("Service catalog",["Forklift Safety","PPE Detection","Loading Bay Safety",
  "Fire & Smoke Detection","Restricted Zones","Video Analytics"]),
 ("Types",["3PL Operators","E-Commerce Fulfilment","Cold Storage","FMCG Distribution",
  "Retail Distribution","Manufacturing Plants"])]
NEGATIVES=[
 ("GPS, telematics and fleet tracking","gps, gps tracking, fleet tracking, vehicle tracking, asset tracking, telematics, tracker, tracking device, gps tracker, fleet management",
  "VERIFIED FROM YOUR OWN ACCOUNT: this is the single largest source of off-target traffic in viAct's warehouse-related history. 'gps tracking for equipment' alone took 174 clicks. Different product entirely."),
 ("Warehouse property and space","warehouse for rent, warehouse for sale, warehouse space, warehouse lease, warehouse rental, industrial unit, storage unit, self storage",
  "From the brief's day-1 list. Property intent, not safety intent."),
 ("Warehouse equipment and fit-out","rack, racking, shelving, pallet, pallet jack, mezzanine, conveyor, dock leveller, dock plate supplier, warehouse equipment",
  "From the brief's day-1 list. Equipment buyers, not software buyers."),
 ("Forklift purchase, hire and parts","forklift for sale, used forklift, forklift hire, forklift rental, forklift price, forklift parts, forklift battery, forklift tyres, forklift dealer",
  "From the brief's day-1 list. High volume and completely off-proposition."),
 ("Jobs, training and certification","job, jobs, vacancy, salary, career, hiring, course, training, certification, licence, license, ticket, osha 10, exam, student",
  "From the brief's day-1 list."),
 ("Documents and free downloads","pdf, template, handbook, checklist, toolbox talk, free, download, sample, example, ppt, poster, signage",
  "From the brief's day-1 list. Research intent, no commercial value."),
 ("Warehouse management software","wms, warehouse management system, inventory software, picking software, order management, stock control, erp",
  "VERIFIED FROM YOUR OWN ACCOUNT: 'warehouse picking software in the usa' produced 7 recorded conversions on a product viAct does not sell. Those were not real leads."),
 ("CCTV and camera hardware brands","hikvision, dahua, uniview, avigilon, axis camera, bosch camera, cctv price, camera price, nvr, dvr, ip camera price",
  "VERIFIED FROM YOUR OWN ACCOUNT: hikvision variants appear repeatedly in warehouse-related search terms. Hardware shoppers, not platform buyers."),
 ("Physical safety products","safety vest, hi vis jacket, hard hat, safety shoes, barrier, bollard, mirror, warning light, beacon, floor marking, ppe supplier",
  "People buying gear, not detection software."),
 ("Competitor brand terms","voxel, intenseye, protex ai, blaxtair, arvist, spot ai, everguard, proxicam",
  "RECOMMENDATION, not a rule. Competitor terms can be valuable in B2B. Start excluded, then test a small separate campaign so the spend is visible and controllable."),
 ("Consumer and domestic","home, house, domestic, garage, diy, personal, hobby","Preventive."),
 ("Autonomous vehicles and robotics","agv, amr, autonomous forklift, robot, robotics, automation supplier, cobot",
  "Adjacent technology, different budget holder and different buying process."),
]
STRUCTURE=[
 ("Campaign name","WH_Search_NL / WH_Search_UK / WH_Search_GCC / WH_Search_APAC",
  "Four Search campaigns, one per market group, exactly as the brief proposes. Separate campaigns keep budget, language and negatives controllable per market."),
 ("Campaign objective","Leads - qualified demo requests from warehouse decision-makers",
  "The brief's success gate is cost per demo below HKD 1,000."),
 ("Campaign type","Search only. Search partners OFF. Display network OFF.",
  "Display expansion on a Search campaign is a known source of low-quality clicks. The brief asks for high intent, so both stay off."),
 ("Target locations","NL: Venlo, Tilburg-Waalwijk, Rotterdam port, Schiphol Trade Park, Eindhoven-Helmond. UK: Northampton, Milton Keynes, Leicester, Rugby DIRFT, London Gateway/Thurrock, Magna Park. GCC: JAFZA, Dubai South, KIZAD, Dubai Industrial City, Al Quoz, Sudair City, Riyadh Second Industrial City, Jeddah Islamic Port, Dammam Third Industrial City. APAC: Shah Alam, Port Klang, Iskandar Puteri, Senai, Bukit Raja.",
  "Taken directly from the brief. Radius targeting of 25-50 km per cluster, as the brief specifies."),
 ("Location targeting approach","Presence only - 'People in or regularly in your targeted locations'. Never 'presence or interest'.",
  "Interest-based targeting is what lets overseas traffic in. viAct's HK campaigns already use presence-only and show 100% in-market traffic as a result."),
 ("Excluded locations","Add Bangladesh, India, Pakistan, Nigeria and the Philippines as campaign exclusions.",
  "RECOMMENDATION. viAct's HK campaigns already exclude the first three, which suggests a prior problem. Presence-only should make this redundant, but it costs nothing as a second layer."),
 ("Audience strategy","Observation only, never targeting. Layer: in-market Enterprise Software; in-market Physical Security & Access Control; in-market Business & Industrial Products; in-market Material Handling Equipment; custom segment built from competitor and category URLs.",
  "Observation lets you read which audiences convert without restricting reach. Do NOT use broad 'all site visitors' remarketing as a signal - that is what diluted HK_Pmax_4S."),
 ("Job titles","Warehouse Director, Warehouse Manager, DC Manager, Operations Director Logistics, Head of HSE/EHS, Supply Chain Operations Director, Loss Prevention Manager",
  "From the brief. Google Search cannot target job titles directly, so these belong in customer-match lists and outbound, not in campaign settings."),
 ("Bidding - weeks 1 to 3","Manual CPC with a bid cap per ad group.",
  "The brief's own 30-day plan says manual CPC in week 2. There is no conversion history in these markets, so automated bidding has nothing to learn from."),
 ("Bidding - week 4 onward","Move an ad group to Maximise Conversions only once it has produced conversions consistently. Add a target CPA only after roughly 30 conversions a month.",
  "Published guidance puts the practical minimum for automated bidding near 30 conversions a month."),
 ("Opening bid caps","Forklift ad group HKD 45. PPE HKD 25. Loading Bay HKD 35. Fire & Smoke HKD 30. Restricted Zone HKD 30. Platform HKD 40.",
  "DERIVED FROM viAct'S OWN ACCOUNT, not from Keyword Planner. Historical cost per click on these exact terms: forklift terms HKD 23-64, PPE terms HKD 13-16, fire detection HKD 13, warehouse AI safety monitoring HKD 64."),
 ("Budget","Weekly per the brief: NL EUR 300, UK GBP 300, GCC AED 1,200, APAC MYR 1,500.",
  "FLAG: the Google Ads account bills in HKD, so these must be converted before entry. I have not invented an exchange rate. Divide the weekly figure by 7 for the daily budget."),
 ("Ad group structure","Six ad groups per campaign, one per module, exactly as the brief specifies - with one change: rename 'Warehouse Video Analytics' to 'Warehouse Safety Platform'.",
  "'Broad AI CCTV catch-all' is how a campaign drifts. HK_Pmax_4S is currently paying for 'food ai' and 'ai chat' for exactly that reason. A platform-level ad group with enterprise terms captures the same buyers without the catch-all."),
 ("Match types","Phrase for coverage, Exact on the head term of each ad group. No broad match at launch.",
  "Broad match with no conversion history and no negative list is the fastest way to spend the pilot budget on the wrong queries."),
 ("Conversion action","One primary action: demo request form on /warehouse-safety. Count ONE per click. Everything else secondary.",
  "A single primary action is what makes cost per demo readable against the brief's HKD 1,000 gate."),
 ("Conversion setup","Enable enhanced conversions. Import qualified-lead status from CRM from week 3.",
  "Without a signal back from sales, bidding optimises toward whoever fills forms most cheaply. That is the documented cause of the lead-quality problem in viAct's existing PMax campaign."),
 ("Form protection","reCAPTCHA v3 plus required business email and company size on the demo form.",
  "The brief's landing page section does not mention form protection. It should, before spend starts."),
 ("Ad rotation","Optimise for best performing ads.",""),
 ("Ad schedule","All days at launch. Review after 14 days.",
  "No prior data in these markets, so restricting hours on day one would be guessing."),
 ("Devices","No bid adjustment at launch. Review at day 14.",
  "viAct's own data shows desktop converting better in B2B, but adjusting before there is data would be premature."),
 ("Performance Max","RECOMMEND DEFERRING the WH_Pmax_Global_WH campaign until the Search pilot has run 30 days.",
  "EVIDENCE-BASED: viAct's existing HK_Pmax_4S has spent HKD 30,324, sends 66% of budget to YouTube and Discover, has produced zero leads from YouTube in eleven months, and is the campaign the team already identifies as the source of low-quality leads. Launching a second PMax before the CRM feedback loop exists repeats that."),
]
LIMITS_OK=True
for lt,d1,d2,u in SITELINKS:
    assert len(lt)<=25,(lt,len(lt)); assert len(d1)<=35 and len(d2)<=35,(d1,d2)
    assert u.startswith("https://www.viact.ai/") and "?" not in u, u
for c in CALLOUTS: assert len(c)<=25,(c,len(c))
for h,v in SNIPPETS:
    assert len(h)<=25 and len(v)>=3
    for x in v: assert len(x)<=25,(x,len(x))
if __name__=="__main__":
    print(f"sitelinks {len(SITELINKS)} | callouts {len(CALLOUTS)} | snippets {len(SNIPPETS)} "
          f"| negative themes {len(NEGATIVES)} | structure rows {len(STRUCTURE)}")
    print("all extension character limits pass")
