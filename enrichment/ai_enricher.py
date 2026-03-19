"""
AI enrichment layer — uses Claude to analyse deal desk submissions + Chorus
call data and surface trends, risks, and wins worth sharing with leadership.
"""

import os
import json
from datetime import date
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-sonnet-4-6"

def _get_client():
    if not _API_KEY:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=_API_KEY)


# ---------------------------------------------------------------------------
# Individual deal analysis
# ---------------------------------------------------------------------------

def _no_ai_deal(deal: dict) -> dict:
    """Fallback when no API key is available — returns basic data from raw fields."""
    churn = deal.get("Churn Threat", "")
    competitor = deal.get("Competitor Pressure", "")
    risk_flags = []
    if churn and str(churn).lower() not in ("", "no", "none", "n/a"):
        risk_flags.append(f"Churn Threat: {churn}")
    if competitor and str(competitor).lower() not in ("", "no", "none", "n/a"):
        risk_flags.append(f"Competitor Pressure: {competitor}")
    return {
        "summary": deal.get("Deal summary", "No summary provided."),
        "risk_flags": risk_flags,
        "opportunities": [],
        "rep_context": deal.get("Deal summary", ""),
        "assigned_to": deal.get("Deal Type", "Unknown"),
    }


def analyse_deal(deal: dict) -> dict:
    """
    Summarise a single deal and flag anything noteworthy.
    Returns a dict with keys: summary, risk_flags, opportunities, rep_context.
    """
    client = _get_client()
    if client is None:
        return _no_ai_deal(deal)

    prompt = f"""You are analysing a DoorDash deal desk renegotiation request. Extract the key signal.

Column reference:
- Mx Name: merchant name
- Deal DRI: the rep/owner handling this deal
- Current DD Partnership Status / Proposed DD Partnership Status: what's changing
- Deal Type: type of deal (use this to infer OAM / IAM / BD team if possible)
- Churn Threat: whether the merchant is at risk of churning
- Competitor Pressure: whether a competitor is involved
- [Post-Sales] Annual GMV: merchant's annual GMV on DoorDash
- Deal summary: rep's written context for the request
- Closure Details / Final Partnership: outcome if already closed

Deal data:
{json.dumps(deal, indent=2, default=str)}

Return a JSON object with exactly these keys:
- summary (2-3 sentence plain English summary of the deal)
- risk_flags (list of strings — churn threat, competitor pressure, GMV at risk, partnership downgrades)
- opportunities (list of strings — retention win, upsell, model deal structure angles)
- rep_context (1 sentence summarising what the Deal DRI said in the deal summary and why it matters)
- assigned_to (the team: OAM / IAM / BD — infer from Deal Type or deal context)

Respond with valid JSON only, no markdown fences."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "summary": raw,
            "risk_flags": [],
            "opportunities": [],
            "rep_context": "",
            "assigned_to": deal.get("Deal Type") or "Unknown",
        }


# ---------------------------------------------------------------------------
# Portfolio-level trend analysis
# ---------------------------------------------------------------------------

def _no_ai_trends(enriched_deals: list[dict], report_date: date) -> dict:
    """Fallback trends when no API key — aggregate basic stats from raw data."""
    from collections import Counter
    churn_count = sum(1 for d in enriched_deals if str(d.get("Churn Threat", "")).lower() not in ("", "no", "none", "n/a"))
    competitor_count = sum(1 for d in enriched_deals if str(d.get("Competitor Pressure", "")).lower() not in ("", "no", "none", "n/a"))
    deal_types = Counter(d.get("Deal Type", "Other") for d in enriched_deals)
    type_str = ", ".join(f"{k}: {v}" for k, v in deal_types.items())
    return {
        "executive_summary": (
            f"{len(enriched_deals)} deals submitted on {report_date.strftime('%B %d, %Y')}. "
            f"Deal type breakdown: {type_str}. "
            f"{churn_count} deals with churn threat, {competitor_count} with competitor pressure. "
            f"AI enrichment was skipped — add ANTHROPIC_API_KEY to .env for full analysis."
        ),
        "top_trends": [],
        "red_flags": [f"Churn threat flagged on {churn_count} deal(s)"] if churn_count else [],
        "wins": [],
        "deal_type_highlights": {k: f"{v} deal(s) of this type submitted today." for k, v in deal_types.items()},
        "recommended_actions": ["Add ANTHROPIC_API_KEY to .env to enable AI-powered analysis."],
    }


def analyse_trends(enriched_deals: list[dict], report_date: date) -> dict:
    """
    Takes the full day's enriched deals (with Chorus call context) and produces
    leadership-ready trend commentary.
    """
    client = _get_client()
    if client is None:
        return _no_ai_trends(enriched_deals, report_date)

    # Build a compact representation to stay within token limits
    compact = []
    for d in enriched_deals:
        chorus_snippets = []
        for call in d.get("chorus_calls", []):
            if call.get("summary"):
                chorus_snippets.append(f"  - Call '{call['title']}' ({call['date']}): {call['summary']}")
        compact.append({
            "merchant": d.get("Mx Name", "Unknown"),
            "deal_dri": d.get("Deal DRI", ""),
            "deal_type": d.get("Deal Type", ""),
            "churn_threat": d.get("Churn Threat", ""),
            "competitor_pressure": d.get("Competitor Pressure", ""),
            "annual_gmv": d.get("[Post-Sales] Annual GMV", ""),
            "current_partnership": d.get("Current DD Partnership Status", ""),
            "proposed_partnership": d.get("Proposed DD Partnership Status", ""),
            "rep_context": d.get("rep_context", ""),
            "ai_summary": d.get("summary", ""),
            "risk_flags": d.get("risk_flags", []),
            "opportunities": d.get("opportunities", []),
            "assigned_to": d.get("assigned_to", ""),
            "chorus_call_summaries": chorus_snippets,
        })

    prompt = f"""You are preparing a daily deal desk briefing for senior sales and commercial leadership.
Date: {report_date.strftime("%B %d, %Y")}
Total deals today: {len(enriched_deals)}

Deal details (JSON):
{json.dumps(compact, indent=2, default=str)}

Analyse the full picture and return a JSON object with exactly these keys:
- executive_summary: 3-4 sentence paragraph suitable for a VP or CRO
- top_trends: list of objects, each with "title" (short) and "detail" (2-3 sentences). Max 5 trends.
- red_flags: list of strings — urgent issues that need escalation today
- wins: list of strings — positive outcomes, retention saves, or model deal structures
- deal_type_highlights: object where each key is a Deal Type ("Mx Retention", "[BD-A] Post-Sales Upgrade", "Mx Renewal") and value is 2-3 sentences of highlights for that group
- recommended_actions: list of 3-5 concrete next steps for leadership

Focus on signal over noise. Pull in Chorus call evidence where it strengthens a point.
Respond with valid JSON only, no markdown fences."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "executive_summary": raw,
            "top_trends": [],
            "red_flags": [],
            "wins": [],
            "deal_type_highlights": {},
            "recommended_actions": [],
        }


# ---------------------------------------------------------------------------
# Main enrichment pipeline
# ---------------------------------------------------------------------------

def enrich_deals(deals: list[dict], report_date: date) -> tuple[list[dict], dict]:
    """
    1. Analyse each deal individually.
    2. Run portfolio-level trend analysis.
    Returns (enriched_deals, trends).
    """
    print(f"[enricher] Analysing {len(deals)} deals individually …")
    enriched = []
    for i, deal in enumerate(deals):
        analysis = analyse_deal(deal)
        enriched.append({**deal, **analysis})
        print(f"[enricher]   {i+1}/{len(deals)} — {analysis.get('assigned_to', '?')} deal analysed")

    print("[enricher] Running portfolio trend analysis …")
    trends = analyse_trends(enriched, report_date)
    print("[enricher] Done.")
    return enriched, trends
