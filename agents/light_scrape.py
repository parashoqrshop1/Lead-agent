"""
Lightweight FREE real scraping for Streamlit Cloud.

No Playwright / no scrapegraphai required:
  1) httpx fetches public HTML
  2) Free Gemini extracts structured independent-shop leads

Also supports multi-query bulk generation helpers.
"""
from __future__ import annotations

import json
import re
from typing import Any, List, Optional
from urllib.parse import quote_plus

import httpx

from agents.lead_schema import (
    EXTRACT_INDEPENDENT_SHOPS_PROMPT,
    SEARCH_INDEPENDENT_PROMPT,
    ShopLead,
)
from agents.qualify_agent import filter_icp, qualify_batch
from agents.storage import log_activity, upsert_leads
from config.niches import niche_label, search_queries_for
from config.settings import get_settings

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36 LeadAgent/1.0"
)


def _strip_html(html: str, max_chars: int = 14000) -> str:
    text = re.sub(r"(?is)<(script|style|noscript|svg).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?is)<!--.*?-->", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&amp;|&lt;|&gt;|&quot;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def fetch_url_text(url: str, timeout: float = 25.0) -> str:
    with httpx.Client(
        follow_redirects=True,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-IN,en;q=0.9"},
    ) as client:
        r = client.get(url)
        r.raise_for_status()
        return _strip_html(r.text)


def _gemini_json(prompt: str) -> Any:
    s = get_settings()
    key = s.get("llm_api_key") or ""
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY missing. Add free key from https://aistudio.google.com/apikey"
        )
    try:
        import google.generativeai as genai
    except ImportError as e:
        raise RuntimeError("pip install google-generativeai") from e

    genai.configure(api_key=key)
    model_name = (s.get("llm_model") or "gemini-2.0-flash").split("/")[-1]
    model = genai.GenerativeModel(model_name)
    resp = model.generate_content(prompt)
    text = (getattr(resp, "text", None) or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        start, end = text.find("["), text.rfind("]")
        if start >= 0 and end > start:
            return {"leads": json.loads(text[start : end + 1])}
        return {}


def _normalize(raw: Any, defaults: dict) -> List[ShopLead]:
    from agents.scraper_agent import _normalize_leads

    return _normalize_leads(raw, defaults=defaults)


def light_extract_url(
    url: str,
    *,
    city: str = "",
    country: str = "",
    niche: str = "clothing",
    save: bool = True,
) -> List[ShopLead]:
    log_activity("light_extract_start", {"url": url})
    page = fetch_url_text(url)
    prompt = (
        EXTRACT_INDEPENDENT_SHOPS_PROMPT
        + f"\n\nCity hint: {city}\nCountry hint: {country}\nNiche hint: {niche}\n"
        + "PAGE TEXT:\n"
        + page
    )
    raw = _gemini_json(prompt)
    leads = _normalize(
        raw,
        {
            "city": city,
            "country": country,
            "niche": niche,
            "category": niche_label(niche),
            "source_url": url,
        },
    )
    leads = filter_icp(qualify_batch(leads), drop_chains=False)
    if save and leads:
        upsert_leads(leads)
    log_activity("light_extract_done", {"count": len(leads), "url": url})
    return leads


def light_search_leads(
    city: str,
    country: str,
    niche: str,
    limit: int = 15,
    save: bool = True,
) -> List[ShopLead]:
    """
    Real-ish free discovery:
    - Build public search URLs (Bing)
    - Fetch HTML text
    - Gemini extracts independent shops
    """
    log_activity("light_search_start", {"city": city, "niche": niche, "limit": limit})
    queries = search_queries_for(niche, city) or [
        f"independent {niche_label(niche)} in {city}"
    ]
    all_leads: List[ShopLead] = []
    errors: List[str] = []

    for q in queries[:3]:
        url = f"https://www.bing.com/search?q={quote_plus(q)}&count=20"
        try:
            page = fetch_url_text(url)
            prompt = (
                SEARCH_INDEPENDENT_PROMPT.format(
                    niche_label=niche_label(niche),
                    city=city,
                    country=country,
                    limit=limit,
                )
                + "\nExtract from this search results text. Prefer local independent shops.\n"
                + "SEARCH RESULTS TEXT:\n"
                + page
            )
            raw = _gemini_json(prompt)
            batch = _normalize(
                raw,
                {
                    "city": city,
                    "country": country,
                    "niche": niche,
                    "category": niche_label(niche),
                    "source_url": f"bing:{q}",
                },
            )
            all_leads.extend(batch)
        except Exception as e:
            errors.append(f"{q}: {e}")

    from agents.storage import dedupe_leads_list

    unique = dedupe_leads_list(filter_icp(qualify_batch(all_leads), drop_chains=False))
    unique = unique[: max(limit, 1)]
    if save and unique:
        upsert_leads(unique)
    log_activity(
        "light_search_done",
        {"count": len(unique), "errors": errors[:5]},
    )
    return unique


def bulk_demo_leads(
    cities: List[str],
    niches: List[str],
    country: str = "India",
    per_combo: int = 12,
    save: bool = True,
) -> List[ShopLead]:
    """Generate many demo leads across cities × niches for UI practice / volume."""
    from agents.scraper_agent import demo_leads

    all_leads: List[ShopLead] = []
    for city in cities:
        for niche in niches:
            batch = demo_leads(city, country, niche, limit=per_combo)
            # drop chain traps from volume runs if desired later; keep for now
            all_leads.extend(batch)
    from agents.storage import dedupe_leads_list

    unique = dedupe_leads_list(qualify_batch(all_leads))
    if save and unique:
        upsert_leads(unique)
    return unique
