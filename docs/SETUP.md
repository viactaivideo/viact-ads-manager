# Connecting Google Ads directly

This is the full credential walkthrough. There are four things to collect:

| # | Credential | Comes from | Time |
|---|---|---|---|
| 1 | Developer token | Your Google Ads **MCC** → API Center | minutes to apply, **1–3 business days** to approve |
| 2 | OAuth client ID + secret | Google Cloud Console | ~10 minutes |
| 3 | Refresh token | The script in this repo | ~2 minutes |
| 4 | Customer IDs | The Google Ads UI | ~1 minute |

Start step 1 first — it is the only one with a waiting period.

---

## 1. Developer token (from the MCC)

The developer token is issued to a **manager (MCC) account**, not to a regular
Google Ads account. One token covers every client account under that manager.

1. Sign in to Google Ads with the MCC: <https://ads.google.com>
2. Confirm the account is a manager account — the UI says "Manager account"
   under the account name. If it does not, create one at
   <https://ads.google.com/home/tools/manager-accounts/> and link your ad
   accounts to it first.
3. Go to **Tools → Setup → API Center**. (API Center only appears for manager
   accounts, and only for users with Administrative access to it.)
4. Copy the **Developer token** shown there.
5. Check the **Access level** next to it. This is the part people get caught by:

   | Access level | What it can do |
   |---|---|
   | **Test account** | Only reads *test* accounts. Real accounts return `DEVELOPER_TOKEN_NOT_APPROVED`. This is the default. |
   | **Basic** | Real accounts, 15,000 operations/day. **This is what you need.** |
   | **Standard** | Real accounts, no practical cap. |

6. If you are on Test-account access, click **Apply for Basic access** and fill
   in the form. Describe the tool honestly — an internal reporting and campaign
   management integration for viAct's own advertising accounts, not a product
   resold to third parties. Approval usually lands in 1–3 business days.

You can complete every other step below while the application is pending; only
live data calls are blocked until it is approved.

---

## 2. OAuth client ID and secret (Google Cloud Console)

The developer token says *which application* is calling. OAuth says *which
Google user* it is acting as. You need both.

1. Open <https://console.cloud.google.com/> and create a project (or reuse one)
   — e.g. `viact-ads-manager`.
2. **APIs & Services → Library**, search for **Google Ads API**, and click
   **Enable**.
3. **APIs & Services → OAuth consent screen**:
   - User type: **Internal** if `viact.ai` is a Google Workspace domain and you
     will only ever authorise viact.ai accounts. Otherwise **External**.
   - Fill in app name, support email, developer contact.
   - **Scopes**: add `https://www.googleapis.com/auth/adwords`.
   - If you chose External, add the Google account you will authorise with as a
     **Test user**.

   > ⚠️ An **External** consent screen left in **Testing** status issues refresh
   > tokens that **expire after 7 days**. Click **Publish app** to move it to
   > Production so your token keeps working. Internal apps are not affected.

4. **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   - Application type: **Desktop app** ← this matters; the refresh-token script
     uses the loopback redirect that only desktop clients allow.
   - Name it, create it, and copy the **Client ID** and **Client secret**.

---

## 3. Refresh token

Run this **on your own machine** — it opens a browser, so it cannot run on a
remote server or in a container.

```bash
git clone https://github.com/viactaivideo/viact-ads-manager.git
cd viact-ads-manager
cp .env.example .env
# put GOOGLE_ADS_CLIENT_ID and GOOGLE_ADS_CLIENT_SECRET into .env first

python3 scripts/get_refresh_token.py
```

The script needs no dependencies (standard library only). It will:

1. Start a temporary listener on `127.0.0.1`.
2. Open Google's consent page.
3. Capture the redirect and exchange the code for tokens.
4. Print the refresh token for you to paste into `.env`.

**Sign in with a Google account that has access to the MCC.** The API can only
see what that user can see in the Google Ads UI.

If it reports that no refresh token was returned, revoke the app at
<https://myaccount.google.com/permissions> and run it again — Google only
returns a refresh token on first consent unless it is forced.

---

## 4. Customer IDs

Two different IDs, and mixing them up is the most common source of
`USER_PERMISSION_DENIED`:

- **`GOOGLE_ADS_LOGIN_CUSTOMER_ID`** — your **MCC** ID. Sent as the
  `login-customer-id` header on every request. It declares which manager
  account authorises the call.
- **`GOOGLE_ADS_CUSTOMER_ID`** — the **client account** whose data you want.
  Optional; it is just the default when a tool call omits `customer_id`.

Both are the 10-digit number in the top-right of the Google Ads UI, **without
dashes**: `123-456-7890` → `1234567890`.

If you only manage one ad account, set `LOGIN_CUSTOMER_ID` to the MCC and
`CUSTOMER_ID` to that account. To discover the account IDs under your MCC, leave
`CUSTOMER_ID` blank and ask Claude to run `list_managed_accounts`.

---

## 5. Fill in `.env`

```bash
GOOGLE_ADS_DEVELOPER_TOKEN=your_token_from_step_1
GOOGLE_ADS_CLIENT_ID=xxxxx.apps.googleusercontent.com
GOOGLE_ADS_CLIENT_SECRET=GOCSPX-xxxxx
GOOGLE_ADS_REFRESH_TOKEN=1//xxxxx
GOOGLE_ADS_LOGIN_CUSTOMER_ID=1234567890
GOOGLE_ADS_CUSTOMER_ID=0987654321
```

`.env` is in `.gitignore`. Keep it that way — the refresh token grants ongoing
access to your ad spend.

---

## 6. Verify

```bash
uv sync
uv run --with pytest --with anyio pytest tests/ -q   # offline checks
```

Then start Claude Code in this directory, approve the `google-ads` MCP server
when prompted, and ask:

> Run check_connection

A healthy response lists your accessible customer IDs. Anything else comes back
with the specific stage that failed and how to fix it.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `DEVELOPER_TOKEN_NOT_APPROVED` | Still on Test-account access. Finish the Basic access application in step 1. |
| `USER_PERMISSION_DENIED` | The authorised user cannot see that account, or `LOGIN_CUSTOMER_ID` is not the manager that owns it. Verify the account is linked under the MCC. |
| `invalid_grant` on every call | Refresh token expired or revoked. If your consent screen is still in Testing, publish it — otherwise tokens die after 7 days. Re-run the script. |
| `NOT_ADS_USER` | You authorised a Google account with no Google Ads profile. Re-run the script and pick the right account. |
| `CUSTOMER_NOT_ENABLED` | The account is cancelled or never finished signup. |
| `RESOURCE_EXHAUSTED` | Hit the 15,000 ops/day Basic-access cap. Wait, or apply for Standard access. |
| MCP server won't start in Claude Code | `uv` must be on your PATH. If Claude Code launches it from a different directory, change `.mcp.json` to `["run", "--directory", "/absolute/path/to/viact-ads-manager", "viact-ads-mcp"]`. |

## Reference

- [Google Ads API — OAuth and HTTP headers](https://developers.google.com/google-ads/api/rest/auth)
- [Google Ads API — developer token access levels](https://developers.google.com/google-ads/api/docs/access-levels)
- [GAQL query language reference](https://developers.google.com/google-ads/api/docs/query/overview)
- [Field reference (v25)](https://developers.google.com/google-ads/api/fields/v25/overview)
