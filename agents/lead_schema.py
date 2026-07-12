"""Lead models without pydantic (Streamlit Cloud Python 3.14-safe)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _is_missing(v: Any) -> bool:
    if v is None:
        return True
    try:
        if v != v:  # NaN
            return True
    except Exception:
        pass
    try:
        import math

        if isinstance(v, float) and math.isnan(v):
            return True
    except Exception:
        pass
    try:
        import pandas as pd

        if pd.isna(v):
            return True
    except Exception:
        pass
    return False


def clean_lead_dict(raw: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    bool_fields = {
        "has_website",
        "is_independent",
        "is_branded_chain",
        "carries_multiple_brands",
        "runs_ads",
        "has_instagram_ads",
        "has_facebook_ads",
        "has_google_ads",
    }
    int_fields = {"lead_score"}

    for k, v in (raw or {}).items():
        if _is_missing(v):
            out[k] = None
            continue
        try:
            import numpy as np

            if isinstance(v, np.generic):
                v = v.item()
        except Exception:
            pass

        if k in bool_fields:
            if isinstance(v, str):
                out[k] = v.strip().lower() in ("true", "1", "yes", "y")
            else:
                out[k] = bool(v)
        elif k in int_fields:
            try:
                out[k] = max(0, min(100, int(float(v))))
            except Exception:
                out[k] = 0
        elif isinstance(v, str):
            out[k] = v
        else:
            if isinstance(v, (int, float, bool, list, dict)):
                out[k] = v
            else:
                out[k] = str(v)

    if not out.get("business_name"):
        out["business_name"] = out.get("name") or "Unknown"
    if not out.get("id"):
        out["id"] = str(uuid4())[:8]
    if out.get("status") in (None, ""):
        out["status"] = "new"
    if out.get("lead_score") is None:
        out["lead_score"] = 0
    return out


def _coerce_bool(v: Any, default: Optional[bool] = None) -> Optional[bool]:
    if _is_missing(v):
        return default
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "1", "yes", "y"):
            return True
        if s in ("false", "0", "no", "n"):
            return False
        return default
    return bool(v)


def _coerce_int(v: Any, default: int = 0) -> int:
    if _is_missing(v):
        return default
    try:
        return max(0, min(100, int(float(v))))
    except Exception:
        return default


def _coerce_str(v: Any, default: Optional[str] = None) -> Optional[str]:
    if _is_missing(v):
        return default
    return str(v)


@dataclass
class ShopLead:
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    business_name: str = ""
    niche: Optional[str] = None
    category: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    whatsapp: Optional[str] = None
    google_maps_url: Optional[str] = None
    has_website: Optional[bool] = None
    website_quality: Optional[str] = None
    is_independent: Optional[bool] = True
    is_branded_chain: Optional[bool] = False
    product_variety: Optional[str] = None
    carries_multiple_brands: Optional[bool] = None
    independence_signals: Optional[str] = None
    runs_ads: Optional[bool] = None
    ad_platforms: Optional[str] = None
    ad_topics: Optional[str] = None
    ad_style: Optional[str] = None
    has_instagram_ads: Optional[bool] = None
    has_facebook_ads: Optional[bool] = None
    has_google_ads: Optional[bool] = None
    ads_evidence: Optional[str] = None
    lead_score: int = 0
    score_breakdown: Optional[str] = None
    score_factors: Optional[str] = None
    pain_points: Optional[str] = None
    experience_fit: Optional[str] = None
    recommended_package: Optional[str] = None
    source_url: Optional[str] = None
    status: str = "new"
    notes: Optional[str] = None
    owner_name: Optional[str] = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def model_validate(cls, data: Any) -> "ShopLead":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            data = {"business_name": str(data)}
        data = clean_lead_dict(data)
        known = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known}
        # coerce core fields
        kwargs["business_name"] = _coerce_str(kwargs.get("business_name"), "Unknown") or "Unknown"
        kwargs["status"] = _coerce_str(kwargs.get("status"), "new") or "new"
        kwargs["id"] = _coerce_str(kwargs.get("id"), str(uuid4())[:8]) or str(uuid4())[:8]
        kwargs["lead_score"] = _coerce_int(kwargs.get("lead_score"), 0)
        for b in (
            "has_website",
            "is_independent",
            "is_branded_chain",
            "carries_multiple_brands",
            "runs_ads",
            "has_instagram_ads",
            "has_facebook_ads",
            "has_google_ads",
        ):
            if b in kwargs:
                default = True if b == "is_independent" else False if b == "is_branded_chain" else None
                kwargs[b] = _coerce_bool(kwargs.get(b), default)
        if not kwargs.get("created_at"):
            kwargs["created_at"] = utc_now()
        if not kwargs.get("updated_at"):
            kwargs["updated_at"] = utc_now()
        return cls(**kwargs)

    @classmethod
    def from_any(cls, raw: Any) -> "ShopLead":
        if isinstance(raw, cls):
            return raw
        if hasattr(raw, "to_dict"):
            raw = raw.to_dict()
        try:
            return cls.model_validate(raw if isinstance(raw, dict) else {"business_name": str(raw)})
        except Exception:
            return cls(business_name=str(getattr(raw, "business_name", raw) or "Unknown"))

    def recompute_score(self) -> int:
        from agents.scoring import apply_score

        apply_score(self)
        return self.lead_score


@dataclass
class ExperienceProposal:
    lead_id: str
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    business_name: str = ""
    niche: Optional[str] = None
    package_name: str = ""
    headline: str = ""
    summary: str = ""
    pillars: List[str] = field(default_factory=list)
    outreach_whatsapp: str = ""
    outreach_email: str = ""
    created_at: str = field(default_factory=utc_now)

    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def model_validate(cls, data: Any) -> "ExperienceProposal":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            data = {}
        known = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known and not _is_missing(v)}
        if "lead_id" not in kwargs:
            kwargs["lead_id"] = str(data.get("lead_id") or "")
        if "pillars" in kwargs and not isinstance(kwargs["pillars"], list):
            kwargs["pillars"] = []
        return cls(**kwargs)


@dataclass
class AgentTask:
    task_type: str
    title: str
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    status: str = "pending"
    params: dict = field(default_factory=dict)
    result_summary: Optional[str] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    lead_ids: List[str] = field(default_factory=list)

    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def model_validate(cls, data: Any) -> "AgentTask":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            data = {}
        known = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known and not _is_missing(v)}
        kwargs.setdefault("task_type", str(data.get("task_type") or "custom"))
        kwargs.setdefault("title", str(data.get("title") or "Untitled"))
        if "params" in kwargs and not isinstance(kwargs["params"], dict):
            kwargs["params"] = {}
        if "lead_ids" in kwargs and not isinstance(kwargs["lead_ids"], list):
            kwargs["lead_ids"] = []
        return cls(**kwargs)


EXTRACT_INDEPENDENT_SHOPS_PROMPT = """
You extract INDEPENDENT local shops for a digital experience / website agency.

TARGET: independent cafés, jewellers, multi-brand clothing, shoe stores, multi-product retail.
EXCLUDE: national/global chains and mono-brand flagships.

For each shop return JSON fields:
business_name, niche (cafe|jeweller|clothing|shoes|multi_retail|other_independent),
category, city, country, address, phone, email, website, instagram, facebook, whatsapp,
google_maps_url, has_website, website_quality (none|poor|average|good),
is_independent, is_branded_chain,
product_variety (low|medium|high), carries_multiple_brands,
independence_signals, pain_points, owner_name, notes,
runs_ads (true/false/null), ad_platforms (e.g. "instagram, facebook"),
ad_topics (what they advertise: products, festival sale, bridal collection, menu...),
ad_style (product_showcase|offer_promo|brand_awareness|mixed|unknown),
has_instagram_ads, has_facebook_ads, has_google_ads, ads_evidence

IMPORTANT: If the shop promotes PRODUCTS in ads/posts (jewellery sets, outfits, shoes, menu items),
set ad_style=product_showcase. These are HIGH VALUE leads.

Return ONLY valid JSON: {"leads": [ ... ]}  Max 20 shops.
"""

ENRICH_SHOP_PROMPT = """
Enrich ONE independent shop for a website + digital experience agency.

Return JSON with:
business_name, niche, category, city, country, address, phone, email, website,
instagram, facebook, whatsapp, owner_name,
has_website, website_quality (none|poor|average|good),
is_independent, is_branded_chain,
product_variety, carries_multiple_brands, independence_signals, pain_points,
experience_fit, recommended_package, notes,
runs_ads, ad_platforms, ad_topics, ad_style (product_showcase|offer_promo|brand_awareness|mixed|unknown),
has_instagram_ads, has_facebook_ads, has_google_ads, ads_evidence

Look for any sign of paid or boosted promotions on Instagram, Facebook, Google.
If ads SHOW products/collections, ad_style MUST be product_showcase.

If branded chain: is_branded_chain=true.
Return ONLY a JSON object.
"""

SEARCH_INDEPENDENT_PROMPT = """
Find INDEPENDENT (non-chain) {niche_label} businesses in {city}, {country}.

Agency sells websites + product showcase experiences to local independent shops.

PRIORITIZE shops that:
- Have Instagram and/or Facebook (paid ads OR organic product posts)
- Post products / collections / menu / jewellery / clothing / footwear
- Are Instagram-only or WhatsApp-only with weak/no website
- Are family-run / boutique / multi-brand / high product variety
- Operate in local markets (not only mall chains)

Avoid chains: Starbucks, Zara, H&M, Tanishq, Bata flagships, Nike mono-stores, big supermarkets.

For each business extract: business_name, niche, category, city, country, address, phone,
email, website, instagram, facebook, whatsapp, has_website, website_quality,
is_independent, is_branded_chain, product_variety, carries_multiple_brands,
independence_signals, pain_points, notes,
runs_ads, ad_platforms, ad_topics, ad_style, has_instagram_ads, has_facebook_ads, has_google_ads, ads_evidence.

If they showcase products on social without clear paid ads, still set ad_style=product_showcase
and note organic social product posts.

Return up to {limit} businesses as JSON {{"leads": [...]}}.
"""

ADS_INTEL_PROMPT = """
You are analyzing a local independent shop's public web/social presence for ADVERTISING signals.

Determine:
1) Do they run or boost ads on Instagram, Facebook, Google, YouTube, or other platforms?
2) What TOPICS do ads/promotions cover?
3) Is the creative PRODUCT-SHOWCASE (showing jewellery, clothes, shoes, menu items, collections)
   or offer/sale, or brand-awareness only?

Return ONLY JSON:
{{
  "runs_ads": true/false,
  "ad_platforms": "instagram, facebook",
  "ad_topics": "short summary of topics",
  "ad_style": "product_showcase|offer_promo|brand_awareness|mixed|unknown",
  "has_instagram_ads": true/false,
  "has_facebook_ads": true/false,
  "has_google_ads": true/false,
  "ads_evidence": "what you saw that indicates ads"
}}

Shop name: {business_name}
City: {city}
Instagram: {instagram}
Facebook: {facebook}
Website: {website}
Known notes: {notes}
"""
