"""Pydantic models for independent-shop leads + multi-agent tasks."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


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
    website_quality: Optional[str] = None  # none | poor | average | good
    is_independent: Optional[bool] = True
    is_branded_chain: Optional[bool] = False
    product_variety: Optional[str] = None  # low | medium | high
    carries_multiple_brands: Optional[bool] = None
    independence_signals: Optional[str] = None
    # ---- Advertising intelligence ----
    runs_ads: Optional[bool] = None
    ad_platforms: Optional[str] = None  # comma list: instagram, facebook, google, youtube
    ad_topics: Optional[str] = None  # what they advertise about
    ad_style: Optional[str] = None  # product_showcase | offer_promo | brand_awareness | mixed
    has_instagram_ads: Optional[bool] = None
    has_facebook_ads: Optional[bool] = None
    has_google_ads: Optional[bool] = None
    ads_evidence: Optional[str] = None
    # ---- Scoring (transparent) ----
    lead_score: int = Field(default=0, ge=0, le=100)
    score_breakdown: Optional[str] = None  # short: "82 | Independent +15; PRODUCT ads +20; ..."
    score_factors: Optional[str] = None  # long detail for Sheets
    # ---- Agency ----
    pain_points: Optional[str] = None
    experience_fit: Optional[str] = None
    recommended_package: Optional[str] = None
    source_url: Optional[str] = None
    status: str = "new"
    notes: Optional[str] = None
    owner_name: Optional[str] = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)

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


# ---------- Prompts ----------

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

Prefer family-run / boutique / multi-brand / high product variety.
Also note if they appear to run Instagram, Facebook, or Google ads — especially product ads.

Avoid chains: Starbucks, Zara, H&M, Tanishq, Bata flagships, Nike mono-stores, big supermarkets.

For each business extract: business_name, niche, category, city, country, address, phone,
email, website, instagram, facebook, whatsapp, has_website, website_quality,
is_independent, is_branded_chain, product_variety, carries_multiple_brands,
independence_signals, pain_points, notes,
runs_ads, ad_platforms, ad_topics, ad_style, has_instagram_ads, has_facebook_ads, has_google_ads, ads_evidence.

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
