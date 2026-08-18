# viact-ads-manager

Direct Google Ads, GA4 and Tag Manager integration for viAct, exposed to Claude
over MCP. See README.md for setup and docs/SETUP.md for credentials.

## Before writing any ad copy

Read **docs/BRAND_CLAIMS.md**. It holds the exact approved wording for viAct's
numeric claims and the list of claims that must not be used. Copy that invents
a statistic, or restates an approved one in different words, is a defect.

## Writing to the account

Every write tool takes `confirm`, defaulting to false. Left false, operations
go to Google with `validateOnly=true` and change nothing. Preview, show the
user, apply only on their word.

Campaigns are never renamed: their names are referenced by reports, saved
filters and the UTM strings baked into live URLs.
