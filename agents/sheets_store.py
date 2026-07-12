"""
Google Sheets lead store — FREE.

Uses a Google Cloud service account (free) + gspread.
All leads (with score + factor breakdown + ads intel) sync to one Sheet.

Setup (phone-friendly): see PHONE_SETUP.md → Google Sheets section.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from agents.lead_schema import ShopLead, utc_now
from agents.storage import log_activity, save_leads
from config.settings import get_settings

# Column order in the Google Sheet (stable for agency ops)
SHEET_HEADERS: List[str] = [
    "id",
    "business_name",
    "niche",
    "category",
    "city",
    "country",
    "phone",
    "whatsapp",
    "email",
    "website",
    "instagram",
    "facebook",
    "has_website",
    "website_quality",
    "is_independent",
    "is_branded_chain",
    "product_variety",
    "carries_multiple_brands",
    "runs_ads",
    "ad_platforms",
    "ad_topics",
    "ad_style",
    "has_instagram_ads",
    "has_facebook_ads",
    "has_google_ads",
    "ads_evidence",
    "lead_score",
    "score_breakdown",
    "score_factors",
    "status",
    "recommended_package",
    "pain_points",
    "experience_fit",
    "independence_signals",
    "owner_name",
    "address",
    "google_maps_url",
    "source_url",
    "notes",
    "created_at",
    "updated_at",
]


def sheets_enabled() -> bool:
    s = get_settings()
    return bool(s.get("google_sheet_id") and s.get("google_service_account_json"))


def sheets_status() -> Dict[str, Any]:
    s = get_settings()
    return {
        "enabled": sheets_enabled(),
        "sheet_id_present": bool(s.get("google_sheet_id")),
        "service_account_present": bool(s.get("google_service_account_json")),
        "worksheet": s.get("google_sheet_worksheet") or "Leads",
    }


def _open_worksheet():
    """Return gspread worksheet or raise with clear message."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as e:
        raise RuntimeError(
            "Install free sheets libs: pip install gspread google-auth"
        ) from e

    s = get_settings()
    sheet_id = s.get("google_sheet_id") or ""
    raw = s.get("google_service_account_json") or ""
    ws_name = s.get("google_sheet_worksheet") or "Leads"

    if not sheet_id or not raw:
        raise RuntimeError(
            "Google Sheets not configured. Set GOOGLE_SHEET_ID and "
            "GOOGLE_SERVICE_ACCOUNT_JSON (full JSON) in secrets."
        )

    info = json.loads(raw) if isinstance(raw, str) else raw
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(ws_name)
    except Exception:
        ws = sh.add_worksheet(title=ws_name, rows=2000, cols=len(SHEET_HEADERS) + 2)
    return ws


def _ensure_headers(ws) -> None:
    values = ws.row_values(1)
    if values != SHEET_HEADERS:
        # If empty or different, reset header row (does not wipe data rows if we only write row 1 when empty)
        if not values:
            ws.update("A1", [SHEET_HEADERS])
        else:
            # Keep existing but ensure our headers if first cell isn't id
            if not values or values[0] != "id":
                ws.insert_row(SHEET_HEADERS, index=1)


def lead_to_row(lead: ShopLead) -> List[Any]:
    data = lead.model_dump()
    row = []
    for h in SHEET_HEADERS:
        v = data.get(h, "")
        if isinstance(v, bool):
            v = "TRUE" if v else "FALSE"
        elif v is None:
            v = ""
        row.append(v)
    return row


def row_to_lead(headers: List[str], row: List[str]) -> Optional[ShopLead]:
    if not row:
        return None
    raw: Dict[str, Any] = {}
    for i, h in enumerate(headers):
        val = row[i] if i < len(row) else ""
        if val in ("TRUE", "True", "true"):
            val = True
        elif val in ("FALSE", "False", "false"):
            val = False
        elif val == "":
            val = None
        raw[h] = val
    if not raw.get("business_name") and not raw.get("id"):
        return None
    # lead_score int
    try:
        if raw.get("lead_score") is not None:
            raw["lead_score"] = int(float(raw["lead_score"]))
    except Exception:
        raw["lead_score"] = 0
    try:
        return ShopLead.model_validate(raw)
    except Exception:
        return None


def push_leads_to_sheets(leads: List[ShopLead]) -> Dict[str, Any]:
    """
    Upsert leads into Google Sheet by id (or business_name+city).
    Full rewrite of data range for simplicity & reliability on free tier.
    """
    if not leads and not sheets_enabled():
        return {"ok": False, "reason": "not_configured"}

    ws = _open_worksheet()
    _ensure_headers(ws)

    # Load existing
    all_values = ws.get_all_values()
    headers = all_values[0] if all_values else SHEET_HEADERS
    existing_rows = all_values[1:] if len(all_values) > 1 else []

    by_id: Dict[str, List[Any]] = {}
    order: List[str] = []
    for row in existing_rows:
        if not row:
            continue
        # pad
        while len(row) < len(headers):
            row.append("")
        lid = row[0] if row else ""
        key = lid or f"row-{len(order)}"
        by_id[key] = row
        order.append(key)

    id_idx = headers.index("id") if "id" in headers else 0
    name_idx = headers.index("business_name") if "business_name" in headers else 1
    city_idx = headers.index("city") if "city" in headers else 4

    def find_key(lead: ShopLead) -> Optional[str]:
        if lead.id and lead.id in by_id:
            return lead.id
        for k, row in by_id.items():
            name = (row[name_idx] if name_idx < len(row) else "").strip().lower()
            city = (row[city_idx] if city_idx < len(row) else "").strip().lower()
            if name == (lead.business_name or "").strip().lower() and city == (
                lead.city or ""
            ).strip().lower():
                return k
        return None

    added = updated = 0
    for lead in leads:
        lead.recompute_score()
        lead.updated_at = utc_now()
        new_row = lead_to_row(lead)
        # Map to sheet header order if headers differ
        if headers != SHEET_HEADERS:
            data = dict(zip(SHEET_HEADERS, new_row))
            new_row = [data.get(h, "") for h in headers]

        key = find_key(lead)
        if key is None:
            key = lead.id
            by_id[key] = new_row
            order.append(key)
            added += 1
        else:
            by_id[key] = new_row
            # ensure id column
            if id_idx < len(new_row):
                by_id[key][id_idx] = lead.id
            updated += 1

    # Write back: clear and bulk update (simple + free-tier friendly)
    out_rows = [headers] + [by_id[k] for k in order if k in by_id]
    ws.clear()
    ws.update("A1", out_rows, value_input_option="USER_ENTERED")

    log_activity("sheets_push", {"added": added, "updated": updated, "total": len(order)})
    return {"ok": True, "added": added, "updated": updated, "total": len(order)}


def pull_leads_from_sheets() -> List[ShopLead]:
    """Load all leads from Sheet into memory models (+ optional local save)."""
    ws = _open_worksheet()
    all_values = ws.get_all_values()
    if not all_values:
        return []
    headers = all_values[0]
    leads: List[ShopLead] = []
    for row in all_values[1:]:
        lead = row_to_lead(headers, row)
        if lead:
            lead.recompute_score()
            leads.append(lead)
    log_activity("sheets_pull", {"count": len(leads)})
    return leads


def sync_local_and_sheets(local_leads: List[ShopLead], direction: str = "push") -> Dict[str, Any]:
    """
    direction:
      push — local → sheets
      pull — sheets → local file
      both — pull merge then push
    """
    if not sheets_enabled():
        return {"ok": False, "reason": "Google Sheets not configured"}

    if direction == "pull":
        leads = pull_leads_from_sheets()
        save_leads(leads)
        return {"ok": True, "direction": "pull", "count": len(leads)}

    if direction == "both":
        remote = pull_leads_from_sheets()
        # merge by id
        by_id = {l.id: l for l in remote}
        for l in local_leads:
            by_id[l.id] = l
        merged = list(by_id.values())
        for l in merged:
            l.recompute_score()
        save_leads(merged)
        result = push_leads_to_sheets(merged)
        result["direction"] = "both"
        result["count"] = len(merged)
        return result

    # push
    for l in local_leads:
        l.recompute_score()
    result = push_leads_to_sheets(local_leads)
    result["direction"] = "push"
    return result
