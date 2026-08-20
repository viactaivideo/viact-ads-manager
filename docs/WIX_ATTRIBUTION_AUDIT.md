# viAct — Wix Lead Attribution & UTM Audit

**Audit only. No website, tracking, campaign, form, tag, or configuration was changed.**
Every write-capable API was called in read mode only.

- **Prepared for:** viAct marketing
- **Date:** 2026-08-20
- **Auditor scope:** Wix (viact.ai + viact.net), GA4 property 252020859, GTM (3 containers), Google Ads 3767588103
- **Access used:** Wix REST API (authenticated, this account), Google Ads/GA4/GTM read APIs, external documentation research
- **Access NOT available:** the live rendered `www.viact.ai` HTML/DOM (blocked by the session's network egress policy), the Wix Inbox UI itself, GTM *version history*, and Google Ads change history. Limitations are called out where they matter.

---

## 1. Executive Summary

**What is happening:** Leads arriving in Wix Inbox carry essentially no campaign attribution (no `utm_source/medium/campaign/term/content`, no `gclid`) because **nothing in the Wix lead-capture path is capable of storing that data on the lead record**, and the one custom script that was added to try is not producing any output.

**Where the data is lost:** At the **Wix form → Wix Inbox / Contact record** boundary. The upstream capture (Google Ads auto-tagging, campaign UTM suffixes, GA4, GTM) is largely healthy and GA4 *does* hold source/medium/campaign for the same sessions. The loss is specifically in what the **Wix form submission writes to the lead**.

**Root cause (STRONGLY SUPPORTED):** viAct's two primary lead forms have **8 fields each, none of which capture attribution**. Wix Forms has no native UTM capture. A custom `<head>` script ("Wix Unknow Source") was added to inject UTMs into the message field, but across **122 consecutive real submissions spanning ~1 month (19 Jul – 20 Aug 2026), 0 contained the script's output marker.** The script is effectively non-functional.

**Why it looks "intermittent":** The deterministic capture path fails **uniformly**, not intermittently. The *appearance* of "sometimes it works" is best explained by (a) leads who type their context into the free-text message, and (b) Wix's own visitor-session "source" shown on the contact card, which is cookie/consent/session-dependent and therefore inconsistent — **not** by UTM capture that toggles on and off. The claim "it worked last month" is **not corroborated** by the Inbox data: the oldest Wix Forms submission on record is 13 Mar 2026 and none, in any month sampled, carry UTMs. What *did* work — and still works — is **GA4/Ads attribution at the aggregate level**, which is a different system from the per-lead Inbox record.

**Secondary, compounding issue (STRONGLY SUPPORTED):** GA4 shows **Direct traffic rising from 16.6% of sessions (Aug 2025) to 50.3% (Aug 2026)**, plus a persistent "Unassigned" bucket and several **malformed manual UTMs** (e.g. `utm_source=EDM&utm_medium=Warehouse`, `July_2026/July_2026`). So even the aggregate attribution that does work is degrading and inconsistently tagged.

**Confidence in the primary root cause: HIGH.**

---

## 2. Current-State Findings (what was actually verified)

| # | Finding | Classification | Evidence source |
|---|---|---|---|
| F1 | Both primary lead forms have exactly 8 fields; none capture UTM/gclid/referrer/landing page | **CONFIRMED** | Wix Form Summary API for forms `cd818a8b…` ("Request A Demo") and `77fa5fda…` |
| F2 | 0 of 122 recent real submissions (19 Jul–20 Aug 2026) contain any `utm_`, `gclid`, or the script's `--- Source ---` marker | **CONFIRMED** | Wix Form Submissions API, 3 batches (63 + 59 covering Jul, + earlier June sample) |
| F3 | An enabled custom `<head>` embed named "Wix Unknow Source" exists specifically to inject UTMs into the message field | **CONFIRMED** | Wix Custom Embeds API — embed id `0edf52d4-7b0b-4943-a882-6a3f0676579d`, `enabled:true` |
| F4 | The Wix contact record stores only `source.sourceType = "WIX_FORMS"` — no campaign data | **CONFIRMED** | Wix Contacts v4 API, contact `4727e694…` |
| F5 | No contact **extended field** for UTM/source exists (21 fields listed; none attribution) | **CONFIRMED** | Wix Extended Fields API |
| F6 | Google Ads **auto-tagging is ON**; enabled campaigns carry `final_url_suffix` UTMs | **CONFIRMED** | Google Ads `customer.auto_tagging_enabled=true`; campaign query |
| F7 | GA4 **does** retain source/medium/campaign for paid & organic sessions | **CONFIRMED** | GA4 `sessionSource/Medium/CampaignName` report |
| F8 | Direct-channel share rose 16.6% → 50.3% of sessions over 12 months | **STRONGLY SUPPORTED** | GA4 monthly `sessionDefaultChannelGroup`, computed |
| F9 | Malformed / non-standard manual UTMs pollute GA4 (e.g. `EDM/Warehouse`, `July_2026`, `GMB/Bio`) | **CONFIRMED** | GA4 source/medium report |
| F10 | Site default consent policy = `analytics:false, advertising:false` (only essential + dataToThirdParty on) | **CONFIRMED** | Wix Site Properties API `consentPolicy` |
| F11 | Two Wix sites (viact.ai / viact.net) and two GTM containers with overlapping/legacy tags | **CONFIRMED** | Wix ListSites; GTM containers |

---

## 3. Attribution Flow Map — where it breaks

```
Ad / Traffic Source
   │  Google Ads auto-tagging (gclid) ✔  + campaign UTM suffix ✔   [HEALTHY]
   ▼
Landing Page (www.viact.ai/…)
   │  URL carries utm_* / gclid ✔                                   [HEALTHY]
   ▼
UTM / GCLID capture in browser
   │  GTM Conversion Linker writes _gcl* cookie ✔ (for Ads)         [HEALTHY]
   │  GA4 records session source/medium/campaign ✔                 [HEALTHY]
   │  NO GTM variable reads utm_* into dataLayer ✗                  [GAP]
   ▼
Session / storage persistence to the form
   │  Custom script saves utm_* to localStorage… but injection      ★ PRIMARY
   │  into the Wix form fails (0/122 submissions carry it) ✗✗✗      BREAK POINT
   ▼
Wix Form submission
   │  Form has NO attribution field to hold it ✗                    ★ ROOT
   ▼
Wix Inbox / Contact record
   │  Stores sourceType="WIX_FORMS" only — no campaign ✗            [DATA ABSENT]
   ▼
GA4 / CRM / Google Ads
      GA4 aggregate attribution intact ✔ ; per-lead identity lost ✗
```

**The break is at the form-write step.** Everything needed arrives at the browser; nothing carries it onto the lead.

---

## 4. Wix Audit

**Sites.** Two published Wix sites on this account:
- **viact.ai** — id `7c4c41cb…`, Editor (classic), Velo enabled, HK/HKD, the site all live Google Ads point to. **This is the lead site.**
- **viact.net** — id `431a4a48…`, Studio editor, IN/INR, created Dec 2024. Separate GTM container (`GTM-WDKCHC5`) with Hotjar + UA + GA4 `G-41BNXDN3Z2` (a *different* GA4 property). Not the ad destination; a source of confusion but not the lead-loss cause.

**Forms (viact.ai).** 8 form schemas exist. The two that produce essentially all leads:
- `cd818a8b…` "Request A Demo" — submit button "Submit"; fields: Full Name, Business Email (blocks free webmail via regex), Phone, Job title, Company, **Message / Pain points** (renders as a text area), Country, consent checkbox. **Revision 24, updated 2026-08-17.**
- `77fa5fda…` — same 8-field shape, different field ids.
- Neither has any hidden field, and **no schema anywhere contains a utm/gclid/source field** (verified: 0 matches for `utm|gclid|referr|campaign|medium|landing` across all schemas; 0 hidden fields).

**Custom embeds (12 total).** Enabled and relevant:
- `GTM-MB6W3RC_head` / `_body` — GTM loader ✔
- `Microsoft Clarity` ✔, `Canonical Tag` (JS-injected canonical), `Enhanced Conversions v4` (pushes `ec_formsubmissions` to dataLayer on Thank-You) ✔
- **`Wix Unknow Source`** — the UTM-injection script (analysed in §5).
- Disabled: Leadfeeder, LinkedIn Insight, two legacy Google Ads gtag snippets. (These being off is fine — GTM handles Ads.)

**Wix Inbox / contact records.** The contact object exposes only `source.sourceType: "WIX_FORMS"`. There is no API field carrying utm/campaign, and no extended field defined to hold one. **Whatever "source" the Inbox UI displays per lead is not campaign attribution from the form** — it is Wix's own visitor-analytics guess, which is session/cookie dependent (see §8, §12).

---

## 5. UTM Audit — the "Wix Unknow Source" script

The enabled `<head>` embed contains this logic (verbatim intent):
1. On page load, read `utm_source/medium/campaign/content/term` + `gclid` from `window.location.search` and save each to `localStorage` (`viact_<key>`).
2. On any click whose element text is one of `submit / send / schedule demo / request a demo / book demo / talk to sales`, build a `--- Source ---` block from localStorage and **append it to every `<textarea>`'s `.value`**, firing an `input` event.

**Empirical result (CONFIRMED): it never produces output.** Across 122 consecutive real submissions (all of Aug to date + all of Jul 2026), **zero** contain `--- Source ---`, `utm_`, or `gclid`. The script is present and enabled but its output has never reached a stored submission in the sampled period.

**Why it fails — the technical defects (LIKELY, cannot be DOM-verified because the live page is not reachable from this environment):**
1. **Wix Forms render as encapsulated components.** Modern Wix form inputs are controlled by Wix's runtime; setting `.value` on the DOM node and dispatching a synthetic `input` event does **not** reliably update the value Wix actually submits. The visible text can change while the submitted payload does not — and here even the visible text isn't landing.
2. **`<textarea>` dependency.** The script writes only to `textarea` elements. Only the demo-type forms have a message text area; **any form without one can never carry a UTM** by this method. Several viAct forms have no long-text field at all.
3. **localStorage is only populated when the landing URL literally contains `utm_*`.** Google Ads auto-tagging adds **`gclid`, not `utm`**, and several enabled campaigns have **no UTM suffix** (e.g. `HK_Pmax_4S` search-partner variants, many paused ones). Organic and direct visitors never have `utm_*`. So for the majority of traffic there is nothing in localStorage to inject even if injection worked.
4. **Timing / capture-phase click handling** is fragile against Wix's own submit handling and the Thank-You re-render.

**Net:** even in the best case this script could only ever tag a minority of visitors (those who arrive with literal `utm_*` in the URL **and** submit a form that has a textarea), and in practice it tags none. There is **no evidence it ever worked** in the Inbox record.

**GTM does not fill the gap:** the `GTM-MB6W3RC` container has **no UTM variables at all** (9 variables, all for enhanced-conversion user data, GADS ID, referrer path). GTM captures nothing UTM-related into any dataLayer field that a form could read.

---

## 6. GA4 Audit

- **Property 252020859**, streams: `viAct.ai` (`G-FMXJP0KJCP`) + `Free Demo` (`G-9LG146J8WQ`, app.viact.ai/signup). GTM loads `G-FMXJP0KJCP`. Consistent. ✔
- **Attribution is intact at session level.** GA4 holds source/medium/campaign for paid and organic (e.g. `google/cpc/GCC_Pmax_4S` 1,265 sessions / 298 key events; `google/organic` 4,186/756). This is the system that "works" — and it is **separate from the Wix lead record**.
- **15 key events**, but the ones actually firing (30 days): `Demo` 1,483, `Contact_Sales` 660, `SSSS_Technical_Guide` 276, `generate_lead` 174. Note `Demo`/`Contact_Sales` fire far more than real form submits (`form_submit` = 12), i.e. several key events are **click-based**, not submission-based — they over-count conversions and are not lead-accurate.
- **Data-quality problems (CONFIRMED):**
  - **Direct 50.3%** of Aug-2026 sessions (was 16.6% a year ago) — a large, growing bucket with no source.
  - **Malformed manual UTMs**: `EDM/Warehouse`, `Fall_Prevention/Fall_Prevention`, `July_2026/July_2026`, `GMB/Bio`, `LinkedIn/Bio` — source and medium set to the same non-standard token, which corrupts channel grouping.
  - `(data not available)` cross-network + `Unassigned` present every month.
- **15 key events is too many** and several duplicate the same intent (`Demo`, `Request_a_demo`, `generate_lead`, `GA4_Lead_Gen`, `ga4_lead_gen`), making conversion reporting ambiguous.

---

## 7. GTM Audit

- **Container `GTM-MB6W3RC` (viact.ai):** 12 tags, 73 triggers, 9 variables.
  - Working: GA4 config (`G-FMXJP0KJCP`), `ga4_leadgen_event`, Google Ads conversion linker, Enhanced Conversions (auto + form user-data), demo-form conversion tags.
  - **No UTM variables, no UTM capture logic.** GTM is not involved in per-lead attribution.
  - Legacy debris: a UA variable (`UA-151182156-1`), a disabled Leadfeeder HTML tag, paused duplicate conversion tags — clutter, not the cause.
- **Container `GTM-WDKCHC5` (viact.net):** GA4 `G-41BNXDN3Z2`, Hotjar, and a still-active **Universal Analytics** pageview tag (UA is deprecated/non-collecting). Separate property; not the lead site.
- **Container `GTM-WN4P74T` (dev.viact.net):** dev.
- **Risk:** two containers + two GA4 properties + two sites invite cross-wiring, but the **ad destination is exclusively `www.viact.ai`**, so this is a hygiene risk, not the current root cause.

---

## 8. Google Ads Audit

- Account **3767588103 "viACT_construction"**, **auto-tagging ON** (gclid appended). ✔
- Enabled campaigns carry `final_url_suffix` UTMs, but **conventions are inconsistent**: some use `utm_source=google`, others `utm_source=google_search` / `google_pmax` / `google_display`; some ad-level final URLs hard-code *yet another* set (`utm_medium=hk_lead_search`), which then **conflicts** with the campaign suffix. This produces the split GA4 rows like `google_search/gcc_search_leads` sitting beside `google/cpc/GCC_Search_Leads`.
- **Interaction with the Inbox problem:** Google Ads passes `gclid` (for Ads conversion import + Enhanced Conversions, which work) but the Wix form stores neither `gclid` nor UTM. So **paid leads land in Inbox indistinguishable from organic/direct.** Ads-side conversion measurement is fine; **per-lead source in the CRM is not.**

---

## 9. Forms / CRM / Integration Audit

- **Wix Forms → Contacts** mapping stores name/email/phone only; the message text area holds free text; **no attribution field is mapped.** (Form `postSubmissionTriggers.upsertContact` maps only name, phone, email.)
- **Pipedrive** (per repo `CLAUDE.md` and `scripts/`) is downstream; the offline-conversion bridge relies on `gclid`/email match. Repo notes already state **Pipedrive stores no Google click id** — consistent with this audit: the click id is never captured at the form, so it can't reach Pipedrive either. This is the same root gap, one system further down.
- No third-party form (HubSpot/Typeform) is in the path for these leads; they are native Wix Forms.

---

## 10. Historical Analysis

- **Oldest Wix Forms submission on record: 2026-03-13** (internal viAct test accounts). Every month sampled since — June, July, August 2026 — shows the **same 8 fields and zero UTMs**. There is **no month in the available data where the Inbox record carried UTMs.** (NOT VERIFIED that it ever did; evidence points to "never" for the Inbox record.)
- **What changed and is measurable:** GA4 **Direct share climbed steadily** (16.6% Aug-25 → 50.3% Aug-26) and AI-assistant traffic appeared (Jun-26+). This is consistent with well-documented 2024–2026 industry trends (privacy/ITP cookie shortening, more app-to-web and AI-referral traffic arriving untagged) rather than a single viAct config change.
- **The "worked last month, not now" perception** most plausibly refers to **GA4/Ads dashboards**, which remain populated, contrasted with **Inbox leads**, which never were — two different systems being conflated. I could not find evidence of a specific historical change that turned Inbox UTM capture off, because the data indicates it was never on. (HYPOTHESIS, flagged as such.)
- **Limitation:** GTM version history and Google Ads change history were not accessible in this session, so I cannot rule out a past working custom-code version. The submission data, however, shows no UTM-bearing leads in any sampled period.

---

## 11. External Research (first-party sources prioritised)

- **Wix Forms has no native UTM capture.** Confirmed by multiple sources; the standard fixes are (a) Wix App Market apps *UTM Catcher* / *Attributer*, or (b) Velo custom code writing UTMs into **hidden form fields**. ([Attributer — capturing UTMs in Wix forms](https://attributer.io/blog/capture-utm-parameters-in-wix-forms); [Wix App Market — UTM Catcher](https://www.wix.com/app-market/web-solution/utm-catcher); [Wix Studio community — passing UTMs through a hidden field](https://forum.wixstudio.com/t/passing-utm-parameters-through-a-hidden-form-field/20029))
- **The supported pattern is hidden fields populated via Velo**, not DOM-injection into a visible textarea. ([gnovelty — capture UTMs in Wix forms with Velo](https://www.gnovelty.com/post/how-to-capture-utm-parameters-and-populate-them-in-wix-forms-using-velo-for-free-forever))
- **Redirect/param-stripping is a real, separate failure mode** (HTTP→HTTPS, non-www→www, trailing-slash canonicalisation can drop the query string). ([bluefroganalytics](https://bluefroganalytics.com/blog/utm-parameters-redirects-killing-attribution/); [Wix URL Redirects help](https://support.wix.com/en/url-redirects-301-redirects-4987556)). This is a plausible *contributor* to Direct-inflation but is **not** the Inbox root cause, since the form has nowhere to store UTMs even when they survive.

Community posts are used as corroboration only; the decisive evidence here is viAct's own submission data and form schemas.

---

## 12. Root-Cause Matrix

| Issue | Evidence | Status | Prob. | Impact | Confirm / disprove |
|---|---|---|---|---|---|
| **Wix forms have no attribution field** | Form Summary API: 8 fields, none UTM; 0 hidden fields | **CONFIRMED** | — | Critical | Already confirmed |
| **Custom UTM script produces no output** | 0/122 submissions carry `--- Source ---`/utm/gclid | **CONFIRMED** | — | Critical | Already confirmed |
| Script defects (controlled-component/shadow DOM, textarea-only, localStorage-only) | Script source + Wix rendering model | **LIKELY** | High | Critical | Live DOM test on viact.ai (not reachable here) |
| **No GTM UTM variable/dataLayer capture** | GTM variables list (9, none UTM) | **CONFIRMED** | — | High | Already confirmed |
| Google Ads passes gclid but form drops it | Auto-tagging on; contact has no gclid; repo notes Pipedrive lacks gclid | **CONFIRMED** | — | High | Already confirmed |
| Direct/Unassigned inflation reduces even aggregate attribution | GA4 16.6%→50.3% Direct | **STRONGLY SUPPORTED** | High | High | GA4 trend (shown) |
| Malformed manual UTMs corrupt channels | `EDM/Warehouse`, `July_2026`, etc. | **CONFIRMED** | — | Medium | Already confirmed |
| Consent policy (analytics/advertising off by default) suppresses some tagging | Site consent `analytics:false, advertising:false`; banner inner `enabled:false` | **HYPOTHESIS** | Medium | Medium | Live consent-mode test + Wix cookie-banner UI check |
| Redirect query-string stripping | External docs; live URL not testable here | **NOT VERIFIED** | Low–Med | Medium | curl the ad final URLs and watch the query survive redirects |
| Two GTM containers / two GA4 / two sites cross-wiring | Inventory | **LIKELY (hygiene)** | Low | Medium | Confirm viact.ai loads only GTM-MB6W3RC + G-FMXJP0KJCP |

---

## 13. Root Cause

**Primary root cause (HIGH confidence):** The Wix lead-capture path has **no mechanism that reliably records campaign attribution on the lead**. Specifically:
1. Wix Forms captures no UTM/gclid natively, and viAct's forms define **no field (hidden or visible) to hold it**; and
2. The one compensating custom script ("Wix Unknow Source") is **non-functional in practice** — 0 of 122 recent submissions carry its output — because it depends on injecting text into Wix's controlled form components via DOM `.value`, only targets textareas, and only has data to inject when the landing URL literally contains `utm_*`.

The failure is **uniform, not intermittent.** The perception of intermittency comes from conflating three different systems: the empty Inbox lead record, the still-working GA4/Ads aggregate attribution, and Wix's own session-based "source" shown on some contact cards (which is genuinely inconsistent because it depends on cookies/consent/session continuity).

**Compounding cause (STRONGLY SUPPORTED):** rising Direct/Unassigned traffic and inconsistent manual UTM tagging degrade even the attribution that GA4 does capture.

---

## 14. Permanent Solution (recommended — NOT implemented)

**Goal:** stamp every lead with its source at submission time, using a supported mechanism.

**A. Capture attribution into hidden fields on every Wix form (the supported pattern).**
1. Add hidden fields to each lead form: `utm_source, utm_medium, utm_campaign, utm_term, utm_content, gclid, wbraid, gbraid, landing_page, referrer, first_touch, last_touch`.
2. Populate them with **Velo** (`wix-location` + `wix-storage`) on the `$w.onReady`/form load — read UTMs and gclid from the URL, persist first-touch and last-touch in local storage, and set the hidden field values through the **Velo form API** (not DOM injection). Velo writes go into the submitted payload reliably; DOM `.value` injection does not.
3. Map those hidden fields to **contact extended fields** so they appear on the contact and export to CRM/Pipedrive.

**B. Retire or replace the "Wix Unknow Source" DOM-injection script** once (A) is live, to avoid double logic. (Do not delete until the replacement is validated.)

**C. Alternative if Velo maintenance is unwanted:** install a vetted Wix App-Market attribution app (UTM Catcher / Attributer) that writes hidden fields. Lower engineering cost, recurring SaaS cost, third-party data-sharing to weigh.

**D. Standardise UTM governance (fixes the GA4 side):**
- One naming convention, lowercase, `source` = platform (`google/linkedin/newsletter`), `medium` = channel type (`cpc/email/social`). Fix `EDM/Warehouse`, `July_2026`, `GMB/Bio` style tags.
- Align Google Ads: pick **one** UTM template at account level and remove conflicting ad-level suffixes so paid rows stop splitting.

**E. Rationalise conversions:** collapse the duplicate lead key events to one canonical `generate_lead` (submission-based, not click-based) so Ads bidding and reports agree.

**F. Consent mode:** implement Google Consent Mode v2 with the Wix banner so analytics/advertising tags degrade gracefully instead of silently under-collecting; verify the default policy isn't suppressing tags for consenting users.

---

## 15. Implementation Plan (for later approval — do not execute now)

1. **Confirm scope on staging/preview**, not live. Enumerate every published form and its submit button.
2. **Add hidden fields** to each form schema (Wix Editor or Forms API) — one set per form.
3. **Write the Velo snippet** (site code) to read URL params + storage and set hidden values via the form/element API; include first- vs last-touch.
4. **Create contact extended fields** for the same keys; map form → contact.
5. **Disable** the "Wix Unknow Source" embed *after* the new path is verified.
6. **Google Ads:** set one account-level tracking template; strip conflicting ad-level UTM suffixes (respecting the CLAUDE.md rule never to rename campaigns).
7. **GA4:** merge duplicate key events to one canonical lead event; leave historical events intact.
8. **Consent Mode v2** wiring with the Wix banner.
9. **Pipedrive bridge:** once `gclid` is captured on the form, extend the existing bridge to read it (addresses the repo's noted gclid gap).

Each step is reversible and should be previewed with `validateOnly`/draft where the API supports it.

---

## 16. Validation Plan

Test a real submission end-to-end and confirm the lead record shows the expected values for each case:

| Scenario | Expected on lead |
|---|---|
| Google Ads (auto-tagged) | `gclid` present; utm_source=google, utm_medium=cpc, correct campaign |
| Other paid (LinkedIn/Bing) | correct utm_source/medium/campaign |
| Organic search | utm_source=(search engine), utm_medium=organic (or documented default) |
| Direct | source=direct/none, landing_page + referrer still recorded |
| Email/EDM | standardised utm_medium=email |
| Different landing pages | landing_page reflects the actual entry URL |
| New vs returning user | first_touch preserved, last_touch updated |
| Desktop + mobile | both populate hidden fields |
| Chrome / Safari / Firefox (ITP/ETP) | values survive; storage fallback works |
| Multi-step / popup forms | hidden fields set before submit |
| Redirect entry (http→https, non-www→www, trailing slash) | UTMs survive to the form (curl the ad final URLs and confirm) |

Pass criterion: **≥95% of test submissions carry the expected attribution**, versus the current 0/122.

---

## 17. Preventive Monitoring

- **Weekly automated check** (extend this repo's tooling): query the last N Wix submissions via the Form Submissions API and alert if the **% carrying a non-empty attribution field drops below a threshold** — the exact test that surfaced this issue (0/122).
- **GA4 guardrail:** monitor Direct + Unassigned share; alert on month-over-month jumps.
- **UTM linter:** validate campaign `final_url_suffix` against the naming convention before launch.
- **Quarterly** reconciliation: GA4 key-event lead count vs Wix Inbox submission count vs Pipedrive deals — divergence flags a broken hop.

---

## 18. Final Conclusion

**The intermittent-attribution symptom has a non-intermittent cause:** Wix leads arrive with no campaign attribution because the form path never stores it — the forms have no attribution field, Wix Forms captures none natively, and the custom injection script has produced zero tagged submissions across a full month of real leads (**CONFIRMED, 0/122**). Upstream capture (Google Ads auto-tagging, campaign UTMs, GA4, GTM conversion linking) is largely healthy, which is why **GA4/Ads dashboards still show source data** while **individual Inbox leads do not** — the two are different systems, and conflating them creates the "sometimes it works" impression. A secondary, real trend — **Direct traffic rising to ~50%** with inconsistent manual UTMs — degrades even the aggregate attribution.

The permanent fix is the Wix-supported pattern: **hidden attribution fields populated by Velo (or a vetted attribution app) at submission time, mapped to contact fields**, plus UTM-naming governance and conversion clean-up.

**Confidence: HIGH** for the primary root cause and the location of loss; **Medium** for the consent-mode and redirect contributors (flagged for live verification, which this environment could not perform).

---

### Evidence appendix — limitations (stated, not filled with assumptions)
- **Live `www.viact.ai` DOM not inspected** — session egress policy blocks the domain (curl → 403; WebFetch → EGRESS_BLOCKED). DOM-level script-failure mechanics are therefore **LIKELY**, not CONFIRMED. The *outcome* (0/122) is CONFIRMED via the Wix API.
- **Wix Inbox UI not directly viewed** — findings about the Inbox record are from the Contacts/Submissions APIs.
- **GTM version history and Google Ads change history not accessible** — historical "did it ever work" is inferred from submission data (no UTM-bearing leads found in any sampled month), not from change logs.
- All Wix write-capable endpoints were used read-only; no create/update/delete calls were made.
