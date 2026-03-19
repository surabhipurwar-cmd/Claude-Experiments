"""
Google Sheets client — pulls all deal desk rows from the configured sheet.
Uses a service account for auth (no browser OAuth needed for scheduled runs).
"""

import os
import json
from datetime import datetime, date
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "11zJTYYvd9On2udbo6EMOOsIggKZ8yncIR0mnjtW5jUc")
SHEET_GID = int(os.getenv("GOOGLE_SHEET_GID", "1224925101"))
SERVICE_ACCOUNT_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "config/service_account.json")


def _get_client() -> gspread.Client:
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_PATH, scopes=SCOPES)
    return gspread.authorize(creds)


def fetch_all_deals() -> list[dict]:
    """Return every row from the deal desk sheet as a list of dicts."""
    gc = _get_client()
    spreadsheet = gc.open_by_key(SHEET_ID)

    # Find the correct worksheet by gid
    worksheet = None
    for ws in spreadsheet.worksheets():
        if ws.id == SHEET_GID:
            worksheet = ws
            break

    if worksheet is None:
        raise ValueError(f"Worksheet with gid={SHEET_GID} not found in spreadsheet {SHEET_ID}")

    records = worksheet.get_all_records()
    print(f"[gsheet] Fetched {len(records)} deal rows")
    return records


def fetch_deals_since(since_date: date) -> list[dict]:
    """
    Return deals from the sheet. The deal desk sheet does not have a submission
    timestamp column, so all rows are returned regardless of since_date.
    Filter downstream by Deal ID range if incremental runs are needed.
    """
    all_deals = fetch_all_deals()
    print(f"[gsheet] Returning all {len(all_deals)} deals (no date column in sheet)")
    return all_deals


def print_columns() -> None:
    """Helper — prints all column names from the sheet. Run once to map the schema."""
    gc = _get_client()
    spreadsheet = gc.open_by_key(SHEET_ID)
    for ws in spreadsheet.worksheets():
        if ws.id == SHEET_GID:
            headers = ws.row_values(1)
            print("Columns:", json.dumps(headers, indent=2))
            return
