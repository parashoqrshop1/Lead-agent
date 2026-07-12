"""
Discover / Enrich agents powered by FREE open-source ScrapeGraphAI + Gemini.

Modes:
  open_source — scrapegraphai library (GitHub MIT) + free Gemini/Groq key
  demo        — offline sample leads (explore UI with zero keys)
  cloud_api   — optional scrapegraph-py (not required for free path)
"""
from __future__ import annotations

import json
from typing import Any, List, Optional
from urllib.parse import quote_plus

from agents.lead_schema import (
    ENRICH_SHOP_PROMPT,
    EXTRACT_INDEPENDENT_SHOPS_PROMPT,
    SEARCH_INDEPENDENT_PROMPT,
    ShopLead,
    utc_now,
)
from agents.qualify_agent import filter_icp, qualify_batch, qualify_lead
from agents.storage import log_activity, upsert_leads
from config.niches import NICHES, REGIONS, niche_label, search_queries_for
from config.settings import get_settings, graph_config


class ScraperError(Exception):
    pass


def _normalize_leads(raw: Any, defaults: Optional[dict] = None) -> List[ShopLead]:
    defaults = defaults or {}
    items: list = []

    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            # try extract JSON object from text
            start, end = raw.find("{"), raw.rfind("}")
            if start >= 0 and end > start:
                try:
                    raw = json.loads(raw[start : end + 1])
                except json.JSONDecodeError:
                    return []
            else:
                return []

    if isinstance(raw, dict):
        for key in ("leads", "businesses", "companies", "results", "data", "items", "shops"):
            if key in raw and isinstance(raw[key], list):
                items = raw[key]
                break
        else:
            if any(k in raw for k in ("business_name", "name", "company_name", "title")):
                items = [raw]
    elif isinstance(raw, list):
        items = raw

    leads: List[ShopLead] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        mapped = {
            "business_name": item.get("business_name")
            or item.get("name")
            or item.get("company_name")
            or item.get("title")
            or "",
            "niche": item.get("niche") or defaults.get("niche"),
            "category": item.get("category") or item.get("industry") or defaults.get("category"),
            "city": item.get("city") or defaults.get("city"),
            "country": item.get("country") or defaults.get("country"),
            "address": item.get("address") or item.get("location"),
            "phone": item.get("phone") or item.get("telephone") or item.get("mobile"),
            "email": item.get("email") or item.get("contact_email"),
            "website": item.get("website") or item.get("site"),
            "instagram": item.get("instagram"),
            "facebook": item.get("facebook"),
            "whatsapp": item.get("whatsapp"),
            "google_maps_url": item.get("google_maps_url") or item.get("maps_url"),
            "has_website": item.get("has_website"),
            "website_quality": item.get("website_quality"),
            "is_independent": item.get("is_independent"),
            "is_branded_chain": item.get("is_branded_chain"),
            "product_variety": item.get("product_variety"),
            "carries_multiple_brands": item.get("carries_multiple_brands"),
            "independence_signals": item.get("independence_signals"),
            "runs_ads": item.get("runs_ads"),
            "ad_platforms": item.get("ad_platforms"),
            "ad_topics": item.get("ad_topics"),
            "ad_style": item.get("ad_style"),
            "has_instagram_ads": item.get("has_instagram_ads"),
            "has_facebook_ads": item.get("has_facebook_ads"),
            "has_google_ads": item.get("has_google_ads"),
            "ads_evidence": item.get("ads_evidence"),
            "pain_points": item.get("pain_points"),
            "experience_fit": item.get("experience_fit"),
            "recommended_package": item.get("recommended_package"),
            "source_url": item.get("source_url") or defaults.get("source_url"),
            "owner_name": item.get("owner_name") or item.get("owner"),
            "notes": item.get("notes") or item.get("description"),
            "status": "new",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        if not mapped["business_name"]:
            continue
        for bool_key in (
            "has_website",
            "is_independent",
            "is_branded_chain",
            "carries_multiple_brands",
            "runs_ads",
            "has_instagram_ads",
            "has_facebook_ads",
            "has_google_ads",
        ):
            v = mapped[bool_key]
            if isinstance(v, str):
                mapped[bool_key] = v.lower() in ("true", "yes", "1")
        try:
            lead = ShopLead.from_any(mapped)
            leads.append(lead)
        except Exception:
            continue
    return leads


# ---------- Open-source ScrapeGraphAI ----------

def oss_smart_scrape(url: str, prompt: str) -> Any:
    try:
        from scrapegraphai.graphs import SmartScraperGraph
    except ImportError as e:
        raise ScraperError(
            "Install open-source ScrapeGraphAI: pip install scrapegraphai && playwright install chromium"
        ) from e

    s = get_settings()
    if not s.get("llm_api_key"):
        raise ScraperError(
            "Free Gemini key missing. Get one at https://aistudio.google.com/apikey "
            "and set GEMINI_API_KEY (or use SCRAPER_MODE=demo)."
        )
    graph = SmartScraperGraph(prompt=prompt, source=url, config=graph_config())
    return graph.run()


def oss_search(prompt: str, max_results: int = 5) -> Any:
    try:
        from scrapegraphai.graphs import SearchGraph
    except ImportError as e:
        raise ScraperError("scrapegraphai not installed") from e

    s = get_settings()
    if not s.get("llm_api_key"):
        raise ScraperError("Free LLM API key missing (GEMINI_API_KEY)")
    cfg = graph_config()
    cfg["max_results"] = max_results
    graph = SearchGraph(prompt=prompt, config=cfg)
    return graph.run()


# ---------- Optional cloud ----------

def cloud_extract_from_url(url: str, prompt: str) -> Any:
    s = get_settings()
    key = s.get("scrapegraph_api_key") or ""
    if not key:
        raise ScraperError("SCRAPEGRAPH_API_KEY missing (cloud mode optional — use open_source)")
    try:
        from scrapegraph_py import Client
    except ImportError as e:
        raise ScraperError("pip install scrapegraph-py for cloud mode") from e
    client = Client(api_key=key)
    try:
        if hasattr(client, "smartscraper"):
            resp = client.smartscraper(website_url=url, user_prompt=prompt)
        else:
            resp = client.smart_scraper(website_url=url, user_prompt=prompt)
        if isinstance(resp, dict):
            return resp.get("result") or resp.get("data") or resp
        return getattr(resp, "result", None) or resp
    finally:
        try:
            client.close()
        except Exception:
            pass


def cloud_search(prompt: str, num_results: int = 10) -> Any:
    s = get_settings()
    key = s.get("scrapegraph_api_key") or ""
    if not key:
        raise ScraperError("SCRAPEGRAPH_API_KEY missing")
    from scrapegraph_py import Client

    client = Client(api_key=key)
    try:
        if hasattr(client, "searchscraper"):
            resp = client.searchscraper(user_prompt=prompt, num_results=num_results)
        else:
            resp = client.search_scraper(user_prompt=prompt, num_results=num_results)
        if isinstance(resp, dict):
            return resp.get("result") or resp.get("data") or resp
        return getattr(resp, "result", None) or resp
    finally:
        try:
            client.close()
        except Exception:
            pass


# ---------- Demo data (zero cost) ----------

def demo_leads(city: str, country: str, niche: str, limit: int = 8) -> List[ShopLead]:
    """Built-in independent shop samples — expands with area variants for volume."""
    base = {
        "cafe": [
            ("Chai & Pages Café", "family-run bookstore café, no website", False, "high",
             {"runs_ads": True, "ad_platforms": "instagram", "ad_style": "product_showcase",
              "ad_topics": "menu items, pastries", "has_instagram_ads": True}),
            ("Roast Theory Coffee", "artisan beans, Instagram only", False, "medium",
             {"runs_ads": True, "ad_platforms": "instagram, facebook", "ad_style": "offer_promo",
              "ad_topics": "happy hour", "has_instagram_ads": True, "has_facebook_ads": True}),
            ("Aunty's Filter Coffee House", "local favourite since 1998", False, "medium",
             {"runs_ads": False}),
            ("Bricklane Bake & Brew", "bakery-café, outdated blogspot", True, "high",
             {"runs_ads": True, "ad_platforms": "google", "ad_style": "product_showcase",
              "ad_topics": "cakes, breads", "has_google_ads": True}),
            ("Neighbourhood Espresso", "independent espresso bar", False, "high",
             {"runs_ads": True, "ad_platforms": "instagram", "ad_style": "product_showcase",
              "ad_topics": "seasonal drinks", "has_instagram_ads": True}),
            ("Corner Cup Collective", "multi-origin beans, weak site", True, "medium",
             {"runs_ads": True, "ad_platforms": "facebook", "ad_style": "mixed",
              "ad_topics": "beans + offers", "has_facebook_ads": True}),
        ],
        "jeweller": [
            ("Shree Lalitha Jewellers", "family goldsmith bridal custom", False, "high",
             {"runs_ads": True, "ad_platforms": "instagram, facebook", "ad_style": "product_showcase",
              "ad_topics": "bridal sets, rings", "has_instagram_ads": True, "has_facebook_ads": True}),
            ("Silver Oak Ornaments", "silver + artificial mix", False, "high",
             {"runs_ads": True, "ad_platforms": "instagram", "ad_style": "product_showcase",
              "ad_topics": "oxidised jewellery", "has_instagram_ads": True}),
            ("Heritage Gems & Co.", "independent average website", True, "medium",
             {"runs_ads": False}),
            ("Mangalam Gold House", "family run multi design variety", False, "high",
             {"runs_ads": True, "ad_platforms": "instagram, google", "ad_style": "product_showcase",
              "ad_topics": "temple jewellery", "has_instagram_ads": True, "has_google_ads": True}),
            ("Pearl & Petal Jewels", "boutique custom orders", False, "medium",
             {"runs_ads": True, "ad_platforms": "facebook", "ad_style": "offer_promo",
              "ad_topics": "festival offer", "has_facebook_ads": True}),
            ("Nagar Silver Works", "high variety silver shop", False, "high",
             {"runs_ads": True, "ad_platforms": "instagram", "ad_style": "product_showcase",
              "ad_topics": "new collections", "has_instagram_ads": True}),
        ],
        "clothing": [
            ("Thread & Loom Boutique", "multi-brand ethnic + western", False, "high",
             {"runs_ads": True, "ad_platforms": "instagram", "ad_style": "product_showcase",
              "ad_topics": "new arrivals lookbook", "has_instagram_ads": True}),
            ("Cotton Street Family Wear", "mens ladies kids variety", False, "high",
             {"runs_ads": True, "ad_platforms": "facebook, google", "ad_style": "offer_promo",
              "ad_topics": "festival sale", "has_facebook_ads": True, "has_google_ads": True}),
            ("Noir Wardrobe", "indie boutique Instagram only", False, "medium",
             {"runs_ads": False}),
            ("Urban Weave Garments", "multi-brand poor mobile site", True, "high",
             {"runs_ads": True, "ad_platforms": "instagram, facebook", "ad_style": "product_showcase",
              "ad_topics": "shirts, kids wear", "has_instagram_ads": True, "has_facebook_ads": True}),
            ("Bazaar Lane Apparels", "mixed brands high variety", False, "high",
             {"runs_ads": True, "ad_platforms": "instagram", "ad_style": "product_showcase",
              "ad_topics": "ethnic + casual", "has_instagram_ads": True}),
            ("Style Chowk Multi Brand", "independent multi brand store", False, "high",
             {"runs_ads": True, "ad_platforms": "facebook", "ad_style": "mixed",
              "ad_topics": "products + sale", "has_facebook_ads": True}),
        ],
        "shoes": [
            ("Sole Brothers Footwear", "multi-brand formal + sports", False, "high",
             {"runs_ads": True, "ad_platforms": "instagram", "ad_style": "product_showcase",
              "ad_topics": "sneakers, school shoes", "has_instagram_ads": True}),
            ("StepLocal Shoe House", "family shoe store since 2004", False, "high",
             {"runs_ads": False}),
            ("Stride Independent", "sneakers + school shoes", True, "medium",
             {"runs_ads": True, "ad_platforms": "google", "ad_style": "brand_awareness",
              "ad_topics": "store awareness", "has_google_ads": True}),
            ("Footprint Multi Brand", "wide footwear variety", False, "high",
             {"runs_ads": True, "ad_platforms": "instagram, facebook", "ad_style": "product_showcase",
              "ad_topics": "new pairs", "has_instagram_ads": True, "has_facebook_ads": True}),
            ("WalkWell Family Shoes", "independent multi product shoes", False, "high",
             {"runs_ads": True, "ad_platforms": "instagram", "ad_style": "offer_promo",
              "ad_topics": "monsoon sale", "has_instagram_ads": True}),
        ],
        "multi_retail": [
            ("Mehta Variety Bazaar", "home gifts toys kitchen", False, "high",
             {"runs_ads": True, "ad_platforms": "facebook, instagram", "ad_style": "product_showcase",
              "ad_topics": "weekly product drops", "has_facebook_ads": True, "has_instagram_ads": True}),
            ("Cornerstone General Store", "neighborhood multi-category", False, "high",
             {"runs_ads": False}),
            ("Lotus Lifestyle Independent", "home + fashion accessories", True, "medium",
             {"runs_ads": True, "ad_platforms": "instagram", "ad_style": "mixed",
              "ad_topics": "decor + offers", "has_instagram_ads": True}),
            ("City Mart Family Store", "multi product variety shop", False, "high",
             {"runs_ads": True, "ad_platforms": "facebook", "ad_style": "product_showcase",
              "ad_topics": "household products", "has_facebook_ads": True}),
            ("Daily Needs Hub", "independent multi department", False, "high",
             {"runs_ads": True, "ad_platforms": "instagram, google", "ad_style": "product_showcase",
              "ad_topics": "groceries + gifts mix", "has_instagram_ads": True, "has_google_ads": True}),
        ],
    }
    rows = list(base.get(niche) or base["clothing"])
    areas = ["Main Market", "Station Road", "Civil Lines", "Old City", "Sector 7", "MG Road"]
    expanded = []
    for area in areas:
        for name, notes, has_web, variety, ads in rows:
            expanded.append((f"{name} — {area}", f"{notes} · {area}", has_web, variety, ads))

    chain_trap = ShopLead(
        business_name=f"Starbucks Reserve Demo Chain ({city})",
        niche="cafe",
        category="coffee chain",
        city=city,
        country=country,
        is_independent=False,
        is_branded_chain=True,
        has_website=True,
        website_quality="good",
        product_variety="low",
        runs_ads=True,
        ad_style="brand_awareness",
        notes="Should be auto-excluded as branded chain",
        source_url="demo://chain-trap",
    )

    out: List[ShopLead] = []
    for name, notes, has_web, variety, ads in expanded[: max(1, limit)]:
        phone_tail = 1000 + (abs(hash(name + city)) % 8000)
        lead = ShopLead(
            business_name=f"{name} ({city})",
            niche=niche,
            category=niche_label(niche),
            city=city,
            country=country,
            phone=(f"+91 98{phone_tail:05d}" if country == "India" else f"+1 555-{phone_tail % 10000:04d}"),
            whatsapp=(f"+91 98{phone_tail:05d}" if country == "India" else None),
            website="https://example-outdated-shop.blogspot.com" if has_web else None,
            has_website=has_web,
            website_quality="poor" if has_web else "none",
            is_independent=True,
            is_branded_chain=False,
            product_variety=variety,
            carries_multiple_brands=variety == "high",
            independence_signals="family run, multi-brand/variety",
            pain_points=notes,
            instagram="https://instagram.com/example_independent",
            source_url="demo://sample",
            notes=notes,
            runs_ads=ads.get("runs_ads"),
            ad_platforms=ads.get("ad_platforms"),
            ad_topics=ads.get("ad_topics"),
            ad_style=ads.get("ad_style"),
            has_instagram_ads=ads.get("has_instagram_ads"),
            has_facebook_ads=ads.get("has_facebook_ads"),
            has_google_ads=ads.get("has_google_ads"),
            ads_evidence=ads.get("ads_evidence"),
        )
        out.append(lead)
    if limit >= 5:
        out.append(chain_trap)
    return qualify_batch(out)[: limit + 1]


# ---------- Public operations ----------

def extract_leads_from_url(
    url: str,
    city: str = "",
    country: str = "",
    niche: str = "",
    category: str = "",
    save: bool = True,
) -> List[ShopLead]:
    s = get_settings()
    mode = s["scraper_mode"]
    log_activity("extract_start", {"url": url, "mode": mode})

    if mode == "demo":
        leads = demo_leads(city or "Demo City", country or "India", niche or "clothing", 6)
    elif mode == "cloud_api":
        raw = cloud_extract_from_url(url, EXTRACT_INDEPENDENT_SHOPS_PROMPT)
        leads = _normalize_leads(
            raw,
            defaults={
                "city": city,
                "country": country,
                "niche": niche,
                "category": category,
                "source_url": url,
            },
        )
    else:
        raw = oss_smart_scrape(url, EXTRACT_INDEPENDENT_SHOPS_PROMPT)
        leads = _normalize_leads(
            raw,
            defaults={
                "city": city,
                "country": country,
                "niche": niche,
                "category": category,
                "source_url": url,
            },
        )

    leads = filter_icp(qualify_batch(leads), drop_chains=False)
    if save and leads:
        upsert_leads(leads)
    log_activity("extract_done", {"url": url, "count": len(leads)})
    return leads


def search_leads(
    city: str,
    country: str,
    niche: str = "clothing",
    limit: int = 10,
    save: bool = True,
) -> List[ShopLead]:
    s = get_settings()
    mode = s["scraper_mode"]
    label = niche_label(niche)
    prompt = SEARCH_INDEPENDENT_PROMPT.format(
        niche_label=label, city=city, country=country, limit=limit
    )
    log_activity("search_start", {"city": city, "niche": niche, "mode": mode})

    if mode == "demo":
        leads = demo_leads(city, country, niche, limit)
    elif mode == "light" or mode == "gemini_web":
        from agents.light_scrape import light_search_leads

        leads = light_search_leads(city, country, niche, limit=limit, save=False)
    elif mode == "cloud_api":
        raw = cloud_search(prompt, num_results=min(limit, 10))
        leads = _normalize_leads(
            raw,
            defaults={
                "city": city,
                "country": country,
                "niche": niche,
                "category": label,
                "source_url": f"search:{niche}@{city}",
            },
        )
    else:
        # open_source: try scrapegraphai, fallback to light gemini fetch
        try:
            raw = oss_search(prompt, max_results=min(limit, 5))
            leads = _normalize_leads(
                raw,
                defaults={
                    "city": city,
                    "country": country,
                    "niche": niche,
                    "category": label,
                    "source_url": f"search:{niche}@{city}",
                },
            )
        except Exception as e:
            log_activity("oss_search_fallback_light", {"error": str(e)})
            from agents.light_scrape import light_search_leads

            leads = light_search_leads(city, country, niche, limit=limit, save=False)

    leads = filter_icp(qualify_batch(leads), drop_chains=False)[:limit]
    if save and leads:
        upsert_leads(leads)
    log_activity("search_done", {"count": len(leads)})
    return leads


def enrich_lead_from_url(url: str, lead: Optional[ShopLead] = None) -> ShopLead:
    s = get_settings()
    mode = s["scraper_mode"]
    if mode == "demo":
        base = lead or ShopLead(business_name="Demo Enriched Shop", city="Demo")
        base.website = url
        base.has_website = True
        base.website_quality = "poor"
        base.experience_fit = "Demo enrichment — connect Gemini + open_source for live pages."
        base = qualify_lead(base)
        upsert_leads([base])
        return base

    if mode == "cloud_api":
        raw = cloud_extract_from_url(url, ENRICH_SHOP_PROMPT)
    else:
        raw = oss_smart_scrape(url, ENRICH_SHOP_PROMPT)

    batch = _normalize_leads(raw, defaults={"source_url": url})
    if batch:
        enriched = batch[0]
    else:
        enriched = lead or ShopLead(business_name="Unknown", source_url=url)

    if lead:
        data = lead.model_dump()
        for k, v in enriched.model_dump().items():
            if k in ("id", "created_at", "status"):
                continue
            if v not in (None, "", [], {}):
                data[k] = v
        data["updated_at"] = utc_now()
        result = ShopLead.model_validate(data)
    else:
        result = enriched

    result = qualify_lead(result)
    upsert_leads([result])
    log_activity("enrich_done", {"id": result.id, "name": result.business_name})
    return result


def run_campaign(
    region: str,
    city: str,
    niche: str,
    limit: int = 10,
    also_search: bool = True,
    drop_chains: bool = True,
) -> dict:
    """
    Multi-agent campaign:
      1) Discover (SearchGraph / demo)
      2) Qualify (chain filter + independence)
      3) Persist
    """
    region = (region or "india").lower()
    country = REGIONS.get(region, {}).get("country", "")
    all_leads: List[ShopLead] = []
    errors: List[str] = []

    if also_search:
        try:
            found = search_leads(
                city=city, country=country or region, niche=niche, limit=limit, save=False
            )
            all_leads.extend(found)
        except Exception as e:
            errors.append(f"search: {e}")

    # Secondary: try a simple public search results page URL pattern (best-effort)
    s = get_settings()
    if s["scraper_mode"] == "open_source" and city:
        q = quote_plus(f"independent {niche_label(niche)} in {city}")
        # Use a static HTML-friendly page when possible; Google often blocks — best effort
        trial_urls = [
            f"https://www.bing.com/search?q={q}",
        ]
        for url in trial_urls[:1]:
            try:
                found = extract_leads_from_url(
                    url, city=city, country=country, niche=niche, save=False
                )
                all_leads.extend(found)
            except Exception as e:
                errors.append(f"url:{url[:40]}: {e}")

    qualified = filter_icp(
        qualify_batch(all_leads),
        drop_chains=drop_chains,
        niches=None,
    )

    # de-dupe
    seen = set()
    unique: List[ShopLead] = []
    for l in qualified:
        k = (l.business_name or "").lower()
        if k and k not in seen:
            seen.add(k)
            unique.append(l)

    if unique:
        upsert_leads(unique)

    return {
        "leads": unique[: limit * 2],
        "count": len(unique),
        "excluded_chains": sum(1 for l in all_leads if l.is_branded_chain),
        "errors": errors,
        "city": city,
        "niche": niche,
        "region": region,
        "queries": search_queries_for(niche, city)[:3],
    }


def health_check() -> dict:
    s = get_settings()
    mode = s["scraper_mode"]
    ok_llm = bool(s.get("llm_api_key"))
    ok_sg = bool(s.get("scrapegraph_api_key"))
    ready = (
        mode == "demo"
        or (mode in ("light", "gemini_web") and ok_llm)
        or (mode == "open_source" and ok_llm)
        or (mode == "cloud_api" and ok_sg)
    )
    sheets = {
        "enabled": bool(s.get("google_sheet_id") and s.get("google_service_account_json")),
        "auto_sync": s.get("sheets_auto_sync"),
    }
    return {
        "scraper_mode": mode,
        "llm_model": s["llm_model"],
        "llm_key_present": ok_llm,
        "scrapegraph_key_present": ok_sg,
        "ready": ready,
        "agency_name": s["agency_name"],
        "free_stack": True,
        "sheets": sheets,
        "stack_note": "Gemini free + open-source ScrapeGraphAI + Google Sheets (or demo mode)",
    }


def suggest_niches() -> List[dict]:
    return [{"id": k, "label": v["label"]} for k, v in NICHES.items()]


def suggest_cities(region: str = "india") -> List[str]:
    return list(REGIONS.get(region, REGIONS["india"]).get("cities", []))
