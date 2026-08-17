# viact-ads-manager

Direct Google Ads API access for Claude — using viAct's own MCC developer token
and OAuth credentials. No third-party data vendor sits between Claude and the
Google Ads API.

Requests go straight to `googleads.googleapis.com` over REST. The only runtime
dependencies are `httpx` and the MCP SDK; there is no protobuf client library to
keep in sync with API versions.

## What it gives Claude

Once connected, Claude can read your Google Ads data in conversation:

> "Which campaigns spent the most last month and what did they convert at?"
> "Show me search terms with over 50 clicks and zero conversions."
> "Compare July against June by campaign."

## Setup

Credentials come from four places. **[docs/SETUP.md](docs/SETUP.md) is the full
walkthrough** — start there, because the developer token needs Google's approval
and that takes 1–3 business days.

The short version:

```bash
git clone https://github.com/viactaivideo/viact-ads-manager.git
cd viact-ads-manager
uv sync

cp .env.example .env          # then add your MCC developer token +
                              # OAuth client ID and secret
python3 scripts/get_refresh_token.py   # run where a browser is;
                                       # paste the result into .env
```

No machine handy to run that on? The refresh token can also be minted entirely
in the browser via Google's OAuth Playground — see
[Path B in docs/SETUP.md](docs/SETUP.md#path-b--in-the-browser-with-the-oauth-playground).
The resulting token is a portable string; where it was created does not matter.

Then open this directory in Claude Code, approve the `google-ads` MCP server,
and ask Claude to **run `check_connection`**.

## Read tools

| Tool | Purpose |
|---|---|
| `check_connection` | End-to-end credential check. Reports which stage failed. |
| `list_accessible_customers` | Accounts these credentials reach directly. |
| `list_managed_accounts` | Expand an MCC into its child accounts. |
| `account_summary` | Account totals: spend, clicks, conversions, CTR, CPC. |
| `campaign_performance` | Per-campaign metrics, sorted by spend. |
| `ad_group_performance` | Per-ad-group metrics. |
| `keyword_performance` | Keywords with match type and Quality Score. |
| `search_terms_report` | Actual queries typed — the basis for negative-keyword work. |
| `ad_performance` | Per-ad metrics, ad strength, final URLs. |
| `run_gaql` | Arbitrary GAQL, for anything the above does not cover. |

Every reporting tool takes:

- `date_range` — a preset (`LAST_7_DAYS`, `LAST_30_DAYS`, `THIS_MONTH`,
  `LAST_MONTH`, …) or an explicit `'2026-07-01,2026-07-31'` range.
- `customer_id` — which account to query; defaults to `GOOGLE_ADS_CUSTOMER_ID`.

Money is returned in micros exactly as Google sends it, with a divided-by-a-million
companion field added alongside: `metrics.cost_micros: "45000000"` arrives with
`metrics.cost: 45.0`.

## Configuration

| Variable | Required | Meaning |
|---|---|---|
| `GOOGLE_ADS_DEVELOPER_TOKEN` | yes | From the MCC's API Center. |
| `GOOGLE_ADS_CLIENT_ID` | yes | OAuth desktop client. |
| `GOOGLE_ADS_CLIENT_SECRET` | yes | OAuth desktop client. |
| `GOOGLE_ADS_REFRESH_TOKEN` | yes | From `scripts/get_refresh_token.py`. |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | for MCC use | Manager account ID, digits only. Sent as `login-customer-id`. |
| `GOOGLE_ADS_CUSTOMER_ID` | no | Default account to query. |
| `GOOGLE_ADS_API_VERSION` | no | Defaults to `v25`. |

Values are read from the environment, falling back to `.env` in the repo root.
`.env` is gitignored.

## Write tools

| Tool | Purpose |
|---|---|
| `set_status` | Pause / enable / remove campaigns, ad groups, keywords, ads |
| `add_negative_keywords` | Block queries at campaign or ad group level |
| `list_negative_keywords` | Existing negatives with the resource names removal needs |
| `remove_negative_keywords` | Remove negatives by resource name |
| `update_campaign_budget` | Change a daily budget |
| `create_campaign_budget` | Create a budget |
| `update_bid` | Set a max CPC on an ad group or keyword |
| `update_bidding_strategy` | Switch bidding strategy, with target CPA / ROAS |
| `create_campaign` | Create a campaign (defaults to PAUSED) |
| `create_ad_group` | Create an ad group |
| `create_responsive_search_ad` | Create an RSA, with length limits checked first |
| `add_keywords` | Add positive keywords |
| `upload_offline_conversions` | Upload conversions against recorded clicks |

Money crosses the tool boundary in **account currency**, never micros. Pass
`175.0`, not `175000000`.

### Preview, then confirm

Every write tool takes `confirm`, defaulting to `false`:

- **`confirm=false`** — the operations go to Google with `validateOnly=true`.
  Google checks them against the real account and changes nothing. The tool
  returns the current state, the exact operations, and Google's verdict.
- **`confirm=true`** — the same payload is applied for real.

Because validation and application send an identical payload, a clean preview
means the apply behaves the same way. A test asserts every write tool defaults
to preview, so a tool cannot be added that applies silently.

Two further guards: new campaigns and ad groups default to `PAUSED`, and
`partialFailure` is off during validation so a bad batch is rejected outright
rather than reported row by row.

### What is deliberately absent

There are no tools for account-structure deletion beyond `set_status REMOVED`,
and none for billing or account settings. Two things are missing because the
API does not expose them: **Auction Insights** (UI only) and **Keyword Planner
forecasts** (a separate service).

## Development

```bash
uv sync
uv run --with pytest --with anyio pytest tests/ -q
```

Tests stub the API with `httpx.MockTransport`, so they run offline and cover GAQL
construction, response flattening, auth-token caching, and error reporting.

## API version

Pinned to **v25** (released July 2026, sunsets August 2027). Bump
`GOOGLE_ADS_API_VERSION` when you move to a newer version; the client builds URLs
from it and does not otherwise depend on the version.
