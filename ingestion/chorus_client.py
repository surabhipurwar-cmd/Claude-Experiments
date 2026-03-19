"""
Chorus.ai client — fetches call recordings and transcripts for merchants.

Auth: Chorus uses OAuth 2.0 / SSO. For automated/scheduled use you need a
long-lived bearer token. Two paths:

  Option A (easiest for personal use):
    1. Log into Chorus in your browser.
    2. Open DevTools → Network tab → find any API request to api.chorus.ai.
    3. Copy the Authorization header value (starts with "Bearer ...").
    4. Paste it into .env as CHORUS_ACCESS_TOKEN.
    Note: these tokens expire (typically 24h–7d). You'll need to refresh manually
    or set up the full OAuth flow (Option B).

  Option B (proper OAuth — ask your Chorus admin for client credentials):
    Set CHORUS_CLIENT_ID and CHORUS_CLIENT_SECRET in .env and uncomment
    the refresh_token() helper below.
"""

import os
from typing import Optional
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("CHORUS_BASE_URL", "https://api.chorus.ai")
ACCESS_TOKEN = os.getenv("CHORUS_ACCESS_TOKEN", "")


def _headers() -> dict:
    if not ACCESS_TOKEN:
        raise EnvironmentError(
            "CHORUS_ACCESS_TOKEN is not set. See ingestion/chorus_client.py for setup steps."
        )
    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def search_calls_for_account(account_name: str, limit: int = 5) -> list[dict]:
    """
    Search Chorus for recent calls mentioning a merchant/account name.
    Returns a list of call metadata dicts.
    """
    url = f"{BASE_URL}/v1/calls"
    params = {
        "accountName": account_name,
        "limit": limit,
        "sortBy": "date",
        "order": "desc",
    }
    resp = requests.get(url, headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    calls = data.get("calls", data.get("data", data.get("results", [])))
    print(f"[chorus] Found {len(calls)} calls for account '{account_name}'")
    return calls


def get_call_transcript(call_id: str) -> Optional[str]:
    """
    Fetch and return the full transcript text for a given call_id.
    Returns None if no transcript is available yet.
    """
    url = f"{BASE_URL}/v1/calls/{call_id}/transcript"
    resp = requests.get(url, headers=_headers(), timeout=15)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()

    # Chorus returns transcript as a list of {speaker, text, startTime} segments
    segments = data.get("transcript", data.get("data", []))
    if not segments:
        return None

    lines = []
    for seg in segments:
        speaker = seg.get("speaker", seg.get("speakerName", "Unknown"))
        text = seg.get("text", seg.get("content", ""))
        lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def get_call_summary(call_id: str) -> Optional[str]:
    """
    Fetch Chorus AI-generated summary for a call (if available on your plan).
    """
    url = f"{BASE_URL}/v1/calls/{call_id}/summary"
    resp = requests.get(url, headers=_headers(), timeout=15)
    if resp.status_code in (404, 403):
        return None
    resp.raise_for_status()
    data = resp.json()
    return data.get("summary") or data.get("data", {}).get("summary")


def fetch_call_context_for_deals(deals: list[dict], calls_per_merchant: int = 3) -> list[dict]:
    """
    For each deal, fetch recent Chorus call data for that merchant.
    Attaches a 'chorus_calls' list to each deal dict and returns the enriched list.

    Expects deal dicts to have a merchant/account field — adjust the key
    after confirming column names from the sheet.
    """
    enriched = []
    for deal in deals:
        merchant = deal.get("Mx Name", "")

        call_data = []
        if merchant:
            try:
                calls = search_calls_for_account(merchant, limit=calls_per_merchant)
                for call in calls:
                    call_id = call.get("id") or call.get("callId")
                    summary = get_call_summary(call_id) if call_id else None
                    call_data.append({
                        "call_id": call_id,
                        "date": call.get("date") or call.get("startTime"),
                        "duration_mins": call.get("durationMs", 0) // 60000,
                        "participants": call.get("participants", []),
                        "summary": summary,
                        "title": call.get("title") or call.get("name"),
                    })
            except Exception as exc:
                print(f"[chorus] Warning — could not fetch calls for '{merchant}': {exc}")

        enriched.append({**deal, "chorus_calls": call_data})
    return enriched
