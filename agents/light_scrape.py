"""
Lightweight FREE real scraping for Streamlit Cloud.

Niche + locality social discovery:
  - Sweep city markets/areas (not only city center)
  - Prefer shops with Instagram/Facebook (ads OR organic product posts)
  - Free Gemini extracts structured independent-shop leads
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
from config.localities import localities_for
from config.niches import niche_label, search_queries_for, social_discovery_queries
from config.settings import get_settings

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36 LeadAgent/1.0"
)

SOCIAL_EXTRACT_EXTRA = """
PRIORITY TARGETS (include aggressively):
- Independent niche shops with Instagram and/or Facebook
- Shops posting products (reels, new arrivals, jewellery sets, outfits, menu items)
- Paid ads OR organic product posts (both are valuable)
- Instagram-only / WhatsApp-only businesses with no real website
- Local market / family shops willing to showcase products online

ALSO set when possible:
- has_social: true if Instagram or Facebook exists
- social_product_posts: true if they show products on social
- marketing_intent: true if no website / social-first / seems open to digital growth

EXCLUDE chains and mono-brand flagships.
Return as many real local shops as possible (up to the requested limit).
"""


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
        raise RuntimeError(
            "google-generativeai is not installed on this host. "
            "Demo mode works without it. For real scrape, use Python 3.12 Cloud "
            "and add google-generativeai to requirements."
        ) from e

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

    leads = _normalize_leads(raw, defaults=defaults)
    # Infer social/product flags from free-text fields when model omits them
    for lead in leads:
        blob = " ".join(
            [
                lead.notes or "",
                lead.pain_points or "",
                lead.ad_topics or "",
                lead.ads_evidence or "",
                lead.independence_signals or "",
            ]
        ).lower()
        if lead.instagram or lead.facebook:
            if not lead.ad_style and any(
                x in blob
                for x in (
                    "product",
                    "collection",
                    "new arrival",
                    "reel",
                    "lookbook",
                    "menu",
                    "catalogue",
                )
            ):
                lead.ad_style = "product_showcase"
            if lead.runs_ads is None and any(
                x in blob for x in ("sponsored", "boost", "ads", "promoted")
            ):
                lead.runs_ads = True
            if "instagram only" in blob or (lead.instagram and not lead.website):
                lead.pain_points = (lead.pain_points or "") + " | social-first / weak website"
        lead.recompute_score()
    return leads


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
        + "\n"
        + SOCIAL_EXTRACT_EXTRA
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
    deep_local: bool = True,
    max_localities: int = 6,
    queries_per_place: int = 3,
) -> List[ShopLead]:
    """
    High-volume niche discovery:
    - city + market localities
    - social-first queries (Instagram/Facebook product shops)
    - Gemini extraction from public search pages
    """
    log_activity(
        "light_search_start",
        {
            "city": city,
            "niche": niche,
            "limit": limit,
            "deep_local": deep_local,
            "max_localities": max_localities,
        },
    )

    places = localities_for(city, max_areas=max_localities) if deep_local else [city]
    all_leads: List[ShopLead] = []
    errors: List[str] = []
    used_queries: List[str] = []

    for place in places:
        queries = social_discovery_queries(niche, place)
        # always include a couple classic queries
        queries = queries[: max(1, queries_per_place)] + search_queries_for(niche, place)[:1]
        # unique
        q_seen = set()
        place_queries = []
        for q in queries:
            k = q.lower()
            if k not in q_seen:
                q_seen.add(k)
                place_queries.append(q)

        for q in place_queries[: queries_per_place]:
            used_queries.append(q)
            url = f"https://www.bing.com/search?q={quote_plus(q)}&count=30"
            try:
                page = fetch_url_text(url)
                prompt = (
                    SEARCH_INDEPENDENT_PROMPT.format(
                        niche_label=niche_label(niche),
                        city=place,
                        country=country,
                        limit=min(limit, 20),
                    )
                    + "\n"
                    + SOCIAL_EXTRACT_EXTRA
                    + f"\nFocus location: {place} (part of {city}).\n"
                    + "Extract LOCAL independent shops with social media if possible.\n"
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
                        "notes": f"locality:{place}",
                    },
                )
                # tag locality in notes if missing
                for lead in batch:
                    if place and place != city and lead.notes and "locality:" not in (lead.notes or ""):
                        lead.notes = f"{lead.notes} | locality:{place}"
                    elif place and not lead.notes:
                        lead.notes = f"locality:{place}"
                all_leads.extend(batch)
            except Exception as e:
                errors.append(f"{q}: {e}")

            # soft stop if we already have enough unique candidates
            if len(all_leads) >= limit * 3:
                break
        if len(all_leads) >= limit * 3:
            break

    from agents.storage import dedupe_leads_list

    unique = dedupe_leads_list(filter_icp(qualify_batch(all_leads), drop_chains=False))
    # Prefer social shops first, then score
    unique.sort(
        key=lambda l: (
            1 if (l.instagram or l.facebook) else 0,
            1 if l.runs_ads else 0,
            l.lead_score or 0,
        ),
        reverse=True,
    )
    unique = unique[: max(limit, 1)]
    if save and unique:
        upsert_leads(unique)
    log_activity(
        "light_search_done",
        {
            "count": len(unique),
            "errors": errors[:8],
            "places": places[:8],
            "queries": used_queries[:12],
        },
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
    from agents.storage import dedupe_leads_list

    all_leads: List[ShopLead] = []
    for city in cities:
        for niche in niches:
            batch = demo_leads(city, country, niche, limit=per_combo)
            all_leads.extend(batch)
    unique = dedupe_leads_list(qualify_batch(all_leads))
    if save and unique:
        upsert_leads(unique)
    return unique


def hyperlocal_demo_leads(
    city: str,
    niches: List[str],
    country: str = "India",
    per_niche: int = 30,
    save: bool = True,
) -> List[ShopLead]:
    """Demo volume across market localities inside one city/town."""
    from agents.scraper_agent import demo_leads
    from agents.storage import dedupe_leads_list

    places = localities_for(city, max_areas=8)
    all_leads: List[ShopLead] = []
    for place in places:
        for niche in niches:
            batch = demo_leads(
                place,
                country,
                niche,
                limit=max(8, per_niche // max(1, len(places)) + 4),
            )
            for lead in batch:
                # normalize city back to parent town for CRM, keep locality in notes
                if city:
                    if lead.city and lead.city != city:
                        lead.notes = f"{lead.notes or ''} | locality:{lead.city}".strip(" |")
                    lead.city = city
            all_leads.extend(batch)
    unique = dedupe_leads_list(qualify_batch(all_leads))
    unique.sort(
        key=lambda l: (
            1 if l.instagram or l.facebook else 0,
            1 if l.runs_ads or (l.ad_style or "").startswith("product") else 0,
            l.lead_score or 0,
        ),
        reverse=True,
    )
    # Keep a healthy local pool (not over-trimmed)
    cap = max(40, per_niche * max(1, len(niches)))
    unique = unique[:cap]
    if save and unique:
        upsert_leads(unique)
    return unique
