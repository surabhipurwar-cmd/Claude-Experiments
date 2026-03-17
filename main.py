"""
main.py — one-shot pipeline run.

Usage:
    python main.py              # run for today
    python main.py --since 2024-03-01   # run for all deals since a date
    python main.py --columns    # just print sheet column names and exit
"""

import argparse
import os
import tempfile
from datetime import date, datetime

from dotenv import load_dotenv

load_dotenv()


def run_pipeline(since: date | None = None) -> str:
    """Execute the full pipeline and return the Google Drive URL of the report."""
    from ingestion.gsheet_client import fetch_all_deals, fetch_deals_since
    from ingestion.chorus_client import fetch_call_context_for_deals
    from enrichment.ai_enricher import enrich_deals
    from report.docx_builder import build_report
    from report.drive_uploader import upload_report

    report_date = date.today()
    since = since or report_date  # default: only today's deals

    print(f"\n{'='*60}")
    print(f"  Deal Desk Daily Report Pipeline")
    print(f"  Report date : {report_date}")
    print(f"  Deals since : {since}")
    print(f"{'='*60}\n")

    # 1. Pull deals from Google Sheet
    print("Step 1/4 — Pulling deals from Google Sheet …")
    if since < report_date:
        deals = fetch_deals_since(since)
    else:
        deals = fetch_deals_since(since)

    if not deals:
        print("No deals found for the period. Exiting.")
        return ""

    # 2. Enrich with Chorus call context
    chorus_token = os.getenv("CHORUS_ACCESS_TOKEN", "")
    if chorus_token:
        print("Step 2/4 — Fetching Chorus call context …")
        deals = fetch_call_context_for_deals(deals)
    else:
        print("Step 2/4 — Skipping Chorus (CHORUS_ACCESS_TOKEN not set)")
        deals = [{**d, "chorus_calls": []} for d in deals]

    # 3. AI enrichment
    print("Step 3/4 — Running AI enrichment via Claude …")
    enriched_deals, trends = enrich_deals(deals, report_date)

    # 4. Build DOCX and upload to Drive
    print("Step 4/4 — Building report and uploading to Google Drive …")
    filename = f"Deal Desk Daily Report — {report_date.strftime('%Y-%m-%d')}.docx"

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        build_report(enriched_deals, trends, report_date, tmp_path)
        drive_url = upload_report(tmp_path, filename)
    finally:
        os.unlink(tmp_path)

    print(f"\nDone! Report available at:\n  {drive_url}\n")
    return drive_url


def print_columns() -> None:
    from ingestion.gsheet_client import print_columns as _print_columns
    _print_columns()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deal Desk Report Pipeline")
    parser.add_argument(
        "--since",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        help="Include deals submitted on or after this date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--columns",
        action="store_true",
        help="Print sheet column names and exit (useful for schema discovery)",
    )
    args = parser.parse_args()

    if args.columns:
        print_columns()
    else:
        run_pipeline(since=args.since)
