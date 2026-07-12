"""Pydantic models for independent-shop leads + multi-agent tasks."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


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
    """Normalize pandas/numpy row dicts so Pydantic never sees NaN."""
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
                out[k] = int(float(v))
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


class ShopLead(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
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
    lead_score: int = Field(default=0, ge=0, le=100)
    score_breakdown: Optional[str] = None
    score_factors: Optional[str] = None
    pain_points: Optional[str] = None
    experience_fit: Optional[str] = None
    recommended_package: Optional[str] = None
    source_url: Optional[str] = None
    status: str = "new"
    notes: Optional[str] = None
    owner_name: Optional[str] = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)

    @field_validator("lead_score", mode="before")
    @classmethod
    def _score_int(cls, v: Any) -> int:
        if _is_missing(v):
            return 0
        try:
            return max(0, min(100, int(float(v))))
        except Exception:
            return 0

    @field_validator(
        "has_website",
        "is_independent",
        "is_branded_chain",
        "carries_multiple_brands",
        "runs_ads",
        "has_instagram_ads",
        "has_facebook_ads",
        "has_google_ads",
        mode="before",
    )
    @classmethod
    def _opt_bool(cls, v: Any) -> Any:
        if _is_missing(v):
            return None
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("true", "1", "yes", "y"):
                return True
            if s in ("false", "0", "no", "n"):
                return False
            return None
        return bool(v)

    @field_validator(
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
        "website_quality",
        "product_variety",
        "independence_signals",
        "ad_platforms",
        "ad_topics",
        "ad_style",
        "ads_evidence",
        "score_breakdown",
        "score_factors",
        "pain_points",
        "experience_fit",
        "recommended_package",
        "source_url",
        "status",
        "notes",
        "owner_name",
        "created_at",
        "updated_at",
        "id",
        mode="before",
    )
    @classmethod
    def _opt_str(cls, v: Any) -> Any:
        if _is_missing(v):
            return None
        if not isinstance(v, str):
            return str(v)
        return v

    @classmethod
    def from_any(cls, raw: Any) -> "ShopLead":
        if isinstance(raw, cls):
            return raw
        if hasattr(raw, "to_dict"):
            raw = raw.to_dict()
        if not isinstance(raw, dict):
            raw = {"business_name": str(raw)}
        data = clean_lead_dict(raw)
        if data.get("business_name") is None:
            data["business_name"] = "Unknown"
        if data.get("status") is None:
            data["status"] = "new"
        if data.get("id") is None:
            data["id"] = str(uuid4())[:8]
        if data.get("created_at") is None:
            data["created_at"] = utc_now()
        if data.get("updated_at") is None:
            data["updated_at"] = utc_now()
        try:
            return cls.model_validate(data)
        except Exception:
            return cls(
                id=str(data.get("id") or str(uuid4())[:8]),
                business_name=str(data.get("business_name") or "Unknown"),
                city=data.get("city"),
                niche=data.get("niche"),
                status=str(data.get("status") or "new"),
                lead_score=int(data.get("lead_score") or 0),
                notes=str(data.get("notes") or "") or None,
            )

    def recompute_score(self) -> int:
        from agents.scoring import apply_score

        apply_score(self)
        return self.lead_score


class ExperienceProposal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    lead_id: str
    business_name: str = ""
    niche: Optional[str] = None
    package_name: str = ""
    headline: str = ""
    summary: str = ""
    pillars: List[str] = Field(default_factory=list)
    outreach_whatsapp: str = ""
    outreach_email: str = ""
    created_at: str = Field(default_factory=utc_now)


class AgentTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    task_type: str
    title: str
    status: str = "pending"
    params: dict = Field(default_factory=dict)
    result_summary: Optional[str] = None
    error: Optional[str] = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    lead_ids: List[str] = Field(default_factory=list)


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
