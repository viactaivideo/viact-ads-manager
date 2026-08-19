#!/usr/bin/env python
"""Send Pipedrive deal outcomes to Google Ads as offline conversions.

    uv run python scripts/pipedrive_to_google_ads.py                  # preview
    uv run python scripts/pipedrive_to_google_ads.py --apply          # upload
    uv run python scripts/pipedrive_to_google_ads.py --days 30 --apply

Needs PIPEDRIVE_API_TOKEN in the environment alongside the Google Ads
credentials. Preview mode contacts Pipedrive but sends Google nothing, so it is
safe to run at any time.

Uploaded conversions feed Smart Bidding, so run the preview and read the skip
reasons before the first real upload.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from viact_ads import bridge  # noqa: E402
from viact_ads.client import GoogleAdsClient  # noqa: E402
from viact_ads.config import load_config  # noqa: E402
from viact_ads.mutations import build_click_conversions  # noqa: E402
from viact_ads.pipedrive import PipedriveClient, PipedriveError  # noqa: E402

# Values, not just counts. A lost deal at zero is what teaches Smart Bidding
# which sources to stop buying; uploading only winners leaves it optimising
# toward whoever fills forms most cheaply.
VALUE_MAP = {"won": 100.0, "lost": 0.0, "open": 20.0}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14, help="how far back to read deals")
    ap.add_argument("--status", default=None, help="won, lost, open, or omit for all")
    ap.add_argument("--conversion-action", default=os.environ.get("PD_CONVERSION_ACTION_ID"),
                    help="Google Ads conversion action id to attribute to")
    ap.add_argument("--gclid-field", default="GCLID",
                    help="name of the Pipedrive custom field holding the click id")
    ap.add_argument("--customer-id", default=None)
    ap.add_argument("--apply", action="store_true", help="actually upload")
    ap.add_argument("--redact", action="store_true",
                    help="print deal ids instead of titles, for logs others can read")
    ap.add_argument("--diagnose", action="store_true",
                    help="report the shape of the Pipedrive data and stop")
    args = ap.parse_args()

    if not args.conversion_action:
        print("No conversion action id. Pass --conversion-action or set "
              "PD_CONVERSION_ACTION_ID.")
        return 2

    since = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")

    try:
        pd = PipedriveClient()
    except PipedriveError as exc:
        print(f"Pipedrive: {exc}")
        return 1
    if args.diagnose:
        try:
            shape = await pd.describe()
        except PipedriveError as exc:
            print(f"Pipedrive: {exc}")
            return 1
        finally:
            await pd.aclose()
        print("=== SHAPE OF THE PIPEDRIVE DATA (no deal contents) ===")
        for key, value in shape.items():
            print(f"  {key:<34} {value}")
        return 0

    try:
        deals = await pd.deals(status=args.status, updated_since=since,
                              gclid_field=args.gclid_field)
    except PipedriveError as exc:
        print(f"Pipedrive: {exc}")
        return 1
    finally:
        await pd.aclose()

    print(f"Pipedrive returned {len(deals)} deals updated in the last {args.days} days.\n")
    result = bridge.prepare(deals, value_map=VALUE_MAP)

    print("=== WILL UPLOAD ===")
    for p in result.prepared:
        if p.skip_reason:
            continue
        v = p.conversion.get("conversion_value")
        label = "" if args.redact else p.title[:44]
        print(f"  deal {p.deal_id:<8} via {p.route:<6} {p.age_days:>3}d old  "
              f"value {v if v is not None else '-':<8} {label}")
    if not result.ready:
        print("  nothing")

    print("\n=== SKIPPED (Google would reject or ignore these) ===")
    if args.redact:
        # One line per reason rather than per deal: the counts are the signal,
        # and the titles are the company's pipeline.
        print("  (titles hidden) see SUMMARY below for counts by reason")
    else:
        for p in result.skipped():
            print(f"  deal {p.deal_id:<8} {p.title[:40]:42} {p.skip_reason}")
    if not result.skipped():
        print("  none")

    print("\n=== SUMMARY ===")
    for k, v in sorted(result.summary().items()):
        print(f"  {k:<52} {v}")

    if not result.ready:
        return 0

    payload = build_click_conversions(
        load_config().resolve_customer_id(args.customer_id),
        str(args.conversion_action),
        result.ready,
    )
    client = GoogleAdsClient(load_config())
    response = await client.upload_click_conversions(
        payload, customer_id=args.customer_id, validate_only=not args.apply
    )
    accepted = len(response.get("results", []))
    print(f"\n{'UPLOADED' if args.apply else 'VALIDATED'} {accepted} of {len(payload)}")
    if not args.apply:
        print("Preview only. Re-run with --apply to send.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
