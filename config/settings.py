"""Central settings — FREE stack defaults (Gemini + open-source ScrapeGraphAI + Sheets)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover

    def load_dotenv(*_a, **_k):
        return False


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
LEADS_CSV = DATA_DIR / "leads.csv"
LEADS_JSON = DATA_DIR / "leads.json"
TASKS_JSON = DATA_DIR / "tasks.json"
ACTIVITY_LOG = DATA_DIR / "activity.jsonl"
PROPOSALS_JSON = DATA_DIR / "proposals.json"

load_dotenv(ROOT / ".env")


def _secret(key: str, default: str = "") -> str:
    """Read Streamlit secret or env. Never crash if secrets missing."""
    try:
        import streamlit as st

        if hasattr(st, "secrets"):
            val = None
            try:
                val = st.secrets.get(key, None)
            except Exception:
                try:
                    val = st.secrets[key]
                except Exception:
                    val = None
            if val is not None:
                if isinstance(val, dict):
                    import json

                    return json.dumps(val)
                text = str(val)
                return text.strip() if key == "DASHBOARD_PASSWORD" else text
    except Exception:
        pass
    env = os.getenv(key)
    if env is None or env == "":
        return default
    return env.strip() if key == "DASHBOARD_PASSWORD" else env


def get_settings() -> dict[str, Any]:
    """Fresh each call — important after secrets changes on Streamlit Cloud."""
    model = _secret("LLM_MODEL", "gemini-2.0-flash")
    api_key = (_secret("GEMINI_API_KEY") or "").strip()
    requested_mode = (_secret("SCRAPER_MODE", "") or "").strip().lower()
    # Real mode only if user asked for light AND key exists; else demo (never silent empty).
    if requested_mode in ("light", "gemini_web", "open_source", "cloud_api") and api_key:
        scraper_mode = requested_mode
    elif requested_mode in ("light", "gemini_web", "open_source", "cloud_api") and not api_key:
        scraper_mode = "demo"  # will warn in UI
    elif requested_mode == "demo" or not requested_mode:
        scraper_mode = "demo"
    else:
        scraper_mode = requested_mode or "demo"

    if not api_key:
        api_key = (_secret("GROQ_API_KEY") or _secret("OPENAI_API_KEY") or "").strip()

    sa_json = _secret("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        sa_path = _secret("GOOGLE_SERVICE_ACCOUNT_FILE")
        if sa_path and Path(sa_path).exists():
            sa_json = Path(sa_path).read_text(encoding="utf-8")

    auto_sheets = _secret("SHEETS_AUTO_SYNC", "false").lower() in ("1", "true", "yes")
    pwd = _secret("DASHBOARD_PASSWORD", "change-me-now") or "change-me-now"

    return {
        "llm_model": model.replace("google_genai/", ""),
        "llm_api_key": api_key,
        "scraper_mode": scraper_mode,
        "scrapegraph_api_key": _secret("SCRAPEGRAPH_API_KEY"),
        "dashboard_password": pwd,
        "agency_name": _secret("AGENCY_NAME", "Your Web Agency"),
        "agency_website": _secret("AGENCY_WEBSITE", "https://your-agency.com"),
        "agency_email": _secret("AGENCY_EMAIL", "hello@your-agency.com"),
        "agency_whatsapp": _secret("AGENCY_WHATSAPP", ""),
        "agency_tagline": _secret(
            "AGENCY_TAGLINE", "Digital experiences for independent shops"
        ),
        "google_sheet_id": _secret("GOOGLE_SHEET_ID"),
        "google_service_account_json": sa_json,
        "google_sheet_worksheet": _secret("GOOGLE_SHEET_WORKSHEET", "Leads"),
        "sheets_auto_sync": auto_sheets,
        "leads_csv": str(LEADS_CSV),
        "leads_json": str(LEADS_JSON),
        "tasks_json": str(TASKS_JSON),
        "activity_log": str(ACTIVITY_LOG),
        "proposals_json": str(PROPOSALS_JSON),
    }


def graph_config() -> dict[str, Any]:
    s = get_settings()
    model = s["llm_model"]
    api_key = s["llm_api_key"]
    llm: dict[str, Any] = {"model": model}
    if api_key:
        llm["api_key"] = api_key
    if "gemini" in model or model.startswith("google_genai"):
        llm.setdefault("temperature", 0)
    return {
        "llm": llm,
        "verbose": False,
        "headless": True,
    }


LEAD_STATUSES = [
    "new",
    "enriching",
    "qualified",
    "experience_pitched",
    "contacted",
    "replied",
    "meeting",
    "proposal_sent",
    "won",
    "lost",
    "excluded_chain",
    "do_not_contact",
]

LEAD_SCHEMA_FIELDS = [
    "business_name",
    "niche",
    "category",
    "city",
    "country",
    "address",
    "phone",
    "email",
    "website",
    "instagram",
    "facebook",
    "whatsapp",
    "google_maps_url",
    "has_website",
    "website_quality",
    "is_independent",
    "is_branded_chain",
    "product_variety",
    "carries_multiple_brands",
    "independence_signals",
    "runs_ads",
    "ad_platforms",
    "ad_topics",
    "ad_style",
    "has_instagram_ads",
    "has_facebook_ads",
    "has_google_ads",
    "ads_evidence",
    "pain_points",
    "experience_fit",
    "recommended_package",
    "lead_score",
    "score_breakdown",
    "score_factors",
    "source_url",
    "status",
    "notes",
    "owner_name",
    "created_at",
    "updated_at",
]
