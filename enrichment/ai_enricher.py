"""
AI enrichment layer — uses Claude to analyse deal desk submissions + Chorus
call data and surface trends, risks, and wins worth sharing with leadership.
"""

import os
import json
from datetime import date
from typing import Any

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Individual deal analysis
# ---------------------------------------------------------------------------

def analyse_deal(deal: dict) -> dict:
    """
    Summarise a single deal and flag anything noteworthy.
    Returns a dict with keys: summary, risk_flags, opportunities, rep_context.
    """
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

def analyse_trends(enriched_deals: list[dict], report_date: date) -> dict:
    """
    Takes the full day's enriched deals (with Chorus call context) and produces
    leadership-ready trend commentary.

    Returns a dict with keys:
      - executive_summary
      - top_trends (list of trend dicts with title + detail)
      - red_flags (list of strings)
      - wins (list of strings)
      - oam_highlights
      - iam_highlights
      - bd_highlights
      - recommended_actions (list of strings)
    """
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
- oam_highlights: 2-3 sentences on OAM deals specifically
- iam_highlights: 2-3 sentences on IAM deals specifically
- bd_highlights: 2-3 sentences on BD renegotiation specialist deals
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
            "oam_highlights": "",
            "iam_highlights": "",
            "bd_highlights": "",
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
