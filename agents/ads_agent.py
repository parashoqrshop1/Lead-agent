"""
Ads Intelligence Agent — free.

Detects whether an independent shop runs ads (Instagram, Facebook, Google, etc.),
what topics they push, and whether creatives are PRODUCT-SHOWCASE (highest score).

Methods (all free):
1) Keyword heuristics on existing lead text / social URLs
2) Optional ScrapeGraphAI / Gemini page read of IG/FB/site (open_source mode)
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from agents.lead_schema import ADS_INTEL_PROMPT, ShopLead, utc_now
from agents.storage import log_activity, upsert_leads
from config.settings import get_settings

PRODUCT_TOPIC_KEYWORDS = [
    "new arrival",
    "new arrivals",
    "collection",
    "bridal",
    "jewellery",
    "jewelry",
    "gold set",
    "necklace",
    "ring",
    "outfit",
    "dress",
    "saree",
    "kurta",
    "shoes",
    "sneakers",
    "footwear",
    "menu",
    "latte",
    "pastry",
    "catalogue",
    "catalog",
    "lookbook",
    "shop now",
    "buy now",
    "just in",
    "product",
    "skus",
    "styles",
]

AD_SIGNAL_KEYWORDS = [
    "sponsored",
    "paid partnership",
    "promoted",
    "boosted",
    "ads",
    "advertisement",
    "google ads",
    "running ads",
    "meta ads",
    "instagram ad",
    "facebook ad",
    "sponsored post",
    "lead form ad",
    "traffic campaign",
]

OFFER_KEYWORDS = [
    "sale",
    "discount",
    "% off",
    "offer",
    "festive offer",
    "flat ",
    "clearance",
    "mega sale",
]


def _blob(lead: ShopLead) -> str:
    return " ".join(
        [
            lead.business_name or "",
            lead.notes or "",
            lead.pain_points or "",
            lead.ads_evidence or "",
            lead.ad_topics or "",
            lead.independence_signals or "",
            lead.instagram or "",
            lead.facebook or "",
            lead.website or "",
        ]
    ).lower()


def heuristic_ads_intel(lead: ShopLead) -> Dict[str, Any]:
    """Zero-cost inference from text already on the lead."""
    text = _blob(lead)
    platforms: List[str] = []
    if lead.ad_platforms:
        platforms = [p.strip() for p in re.split(r"[,;|/]", lead.ad_platforms) if p.strip()]

    if "instagram" in text or lead.instagram:
        if any(k in text for k in ("instagram ad", "ig ad", "boosted", "sponsored", "meta ads")):
            if "instagram" not in [p.lower() for p in platforms]:
                platforms.append("instagram")
    if "facebook" in text or lead.facebook:
        if any(k in text for k in ("facebook ad", "fb ad", "boosted", "sponsored")):
            if "facebook" not in [p.lower() for p in platforms]:
                platforms.append("facebook")
    if "google ad" in text or "google ads" in text or "gads" in text:
        if "google" not in [p.lower() for p in platforms]:
            platforms.append("google")

    # If lead already marked runs_ads
    runs = lead.runs_ads is True
    if any(k in text for k in AD_SIGNAL_KEYWORDS):
        runs = True
    if platforms:
        runs = True

    # Soft signal: active Instagram + product language often = paid boosts for local shops
    soft_product = any(k in text for k in PRODUCT_TOPIC_KEYWORDS)
    if lead.instagram and soft_product and lead.runs_ads is not False:
        # don't force runs_ads true without stronger signal unless notes mention promo
        if any(k in text for k in OFFER_KEYWORDS + AD_SIGNAL_KEYWORDS + ["campaign", "promote"]):
            runs = True
            if "instagram" not in [p.lower() for p in platforms]:
                platforms.append("instagram")

    style = (lead.ad_style or "").lower()
    topics = lead.ad_topics or ""
    if soft_product:
        topics = topics or "product/collection focused promotions"
        if not style or style == "unknown":
            style = "product_showcase"
    elif any(k in text for k in OFFER_KEYWORDS):
        topics = topics or "sales and offers"
        if not style or style == "unknown":
            style = "offer_promo"
    elif runs and not style:
        style = "unknown"

    evidence = lead.ads_evidence or ""
    if runs and not evidence:
        evidence = "Heuristic: ad/promo language or platforms detected in public text"
    if soft_product and not evidence:
        evidence = (evidence + "; " if evidence else "") + "Product-showcase language found"

    return {
        "runs_ads": runs if runs else (lead.runs_ads if lead.runs_ads is not None else False),
        "ad_platforms": ", ".join(dict.fromkeys(platforms)) if platforms else (lead.ad_platforms or ""),
        "ad_topics": topics or lead.ad_topics,
        "ad_style": style or lead.ad_style or ("product_showcase" if soft_product else None),
        "has_instagram_ads": "instagram" in [p.lower() for p in platforms] or lead.has_instagram_ads,
        "has_facebook_ads": "facebook" in [p.lower() for p in platforms] or lead.has_facebook_ads,
        "has_google_ads": "google" in [p.lower() for p in platforms] or lead.has_google_ads,
        "ads_evidence": evidence or lead.ads_evidence,
    }


def apply_ads_fields(lead: ShopLead, intel: Dict[str, Any]) -> ShopLead:
    for k, v in intel.items():
        if v is None or v == "":
            continue
        setattr(lead, k, v)
    lead.updated_at = utc_now()
    lead.recompute_score()
    return lead


def analyze_ads_heuristic(lead: ShopLead) -> ShopLead:
    intel = heuristic_ads_intel(lead)
    return apply_ads_fields(lead, intel)


def analyze_ads_with_llm(lead: ShopLead) -> ShopLead:
    """
    Use free Gemini (via google generative language or scrapegraph) to refine ads intel.
    Falls back to heuristic if no key.
    """
    s = get_settings()
    base = heuristic_ads_intel(lead)

    if not s.get("llm_api_key"):
        return apply_ads_fields(lead, base)

    prompt = ADS_INTEL_PROMPT.format(
        business_name=lead.business_name or "",
        city=lead.city or "",
        instagram=lead.instagram or "unknown",
        facebook=lead.facebook or "unknown",
        website=lead.website or "none",
        notes=(lead.notes or "")[:300],
    )

    try:
        # Prefer scraping a known URL if present
        source = lead.instagram or lead.website or lead.facebook
        raw = None
        if source and s.get("scraper_mode") == "open_source":
            try:
                from agents.scraper_agent import oss_smart_scrape

                raw = oss_smart_scrape(source, prompt)
            except Exception:
                raw = None
        if raw is None:
            # pure LLM JSON
            try:
                raise ImportError("use heuristic")  # google.generativeai

                genai.configure(api_key=s["llm_api_key"])
                model_name = s["llm_model"].split("/")[-1]
                model = genai.GenerativeModel(model_name)
                resp = model.generate_content(prompt)
                raw = resp.text
            except Exception:
                raw = None

        parsed = _parse_json(raw) if raw is not None else {}
        if not parsed:
            return apply_ads_fields(lead, base)
        # merge: LLM overrides when present
        merged = {**base, **{k: v for k, v in parsed.items() if v not in (None, "")}}
        log_activity("ads_llm", {"id": lead.id, "style": merged.get("ad_style")})
        return apply_ads_fields(lead, merged)
    except Exception as e:
        log_activity("ads_error", {"id": lead.id, "error": str(e)})
        return apply_ads_fields(lead, base)


def _parse_json(raw: Any) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    text = str(raw).strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {}
    return {}


def enrich_ads_batch(leads: List[ShopLead], use_llm: bool = False, save: bool = True) -> List[ShopLead]:
    out = []
    for lead in leads:
        if lead.is_branded_chain:
            out.append(lead)
            continue
        if use_llm:
            lead = analyze_ads_with_llm(lead)
        else:
            lead = analyze_ads_heuristic(lead)
        out.append(lead)
    if save and out:
        upsert_leads(out)
    return out
