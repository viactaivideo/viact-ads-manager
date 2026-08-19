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

## Pipedrive to Google Ads bridge

`scripts/pipedrive_to_google_ads.py` reads deals from Pipedrive and uploads
them as offline conversions, so Smart Bidding optimises toward leads sales
actually valued rather than toward whoever fills forms most cheaply.

Run it in preview first. It contacts Pipedrive but sends Google nothing:

    uv run python scripts/pipedrive_to_google_ads.py --days 14
    uv run python scripts/pipedrive_to_google_ads.py --days 14 --apply

Google discards conversions whose originating click is too old — 90 days for
a click id, 63 for an email match — so `bridge.prepare` filters on age and
reports every skip. A bridge that uploads everything looks like it worked and
changes nothing.

Lost deals upload at value 0 rather than being withheld. That is what teaches
bidding which sources to stop buying.
