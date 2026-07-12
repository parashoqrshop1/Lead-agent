"""
Transparent lead scoring engine.

Every point is explained so the dashboard + Google Sheets show WHY a lead scored high.
Product-advertising shops (Instagram/Facebook/Google ads showing products) rank highest.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from agents.lead_schema import ShopLead

# Human-readable factor catalogue (also shown in dashboard)
SCORE_FACTOR_GUIDE: List[Dict[str, Any]] = [
    {
        "factor": "Branded chain",
        "points": 0,
        "rule": "If shop is a national/global chain → total score forced to 0 (excluded).",
    },
    {
        "factor": "Base",
        "points": 10,
        "rule": "Every non-chain business starts with 10 points.",
    },
    {
        "factor": "Independent shop",
        "points": 15,
        "rule": "+15 if independent / family / boutique; −20 if clearly not independent.",
    },
    {
        "factor": "Product variety",
        "points": "8–12",
        "rule": "high variety +12 · medium +8 · low +0.",
    },
    {
        "factor": "Multi-brand inventory",
        "points": 10,
        "rule": "+10 if shop carries multiple brands / mixed labels.",
    },
    {
        "factor": "Website gap",
        "points": "3–14",
        "rule": "no website +14 · poor +11 · average +7 · good +3 (still sell experience upgrades).",
    },
    {
        "factor": "Runs paid ads (any platform)",
        "points": 12,
        "rule": "+12 if evidence of Instagram / Facebook / Google / YouTube / Meta ads.",
    },
    {
        "factor": "PRODUCT advertising style",
        "points": 20,
        "rule": "+20 if ads SHOW PRODUCTS (catalogue, new arrival, jewellery set, menu item, footwear). HIGHEST boost — they already spend to sell products and need a site/experience that converts.",
    },
    {
        "factor": "Offer / promo ads",
        "points": 10,
        "rule": "+10 if ads are discount/sale focused (still strong buyer intent).",
    },
    {
        "factor": "Brand-awareness ads only",
        "points": 5,
        "rule": "+5 if ads are lifestyle/brand only without product push.",
    },
    {
        "factor": "Instagram ads",
        "points": 6,
        "rule": "+6 specifically for Instagram/Meta ad activity.",
    },
    {
        "factor": "Facebook ads",
        "points": 4,
        "rule": "+4 for Facebook page ads / boosts.",
    },
    {
        "factor": "Google ads",
        "points": 4,
        "rule": "+4 for Google Search/Maps ads.",
    },
    {
        "factor": "Other ad platforms",
        "points": 3,
        "rule": "+3 for YouTube / TikTok / Snapchat etc.",
    },
    {
        "factor": "Ads + weak web (conversion gap)",
        "points": 10,
        "rule": "+10 if they run ads BUT website is missing/poor — money wasted without a landing experience.",
    },
    {
        "factor": "Phone / WhatsApp",
        "points": 8,
        "rule": "+8 if callable / WhatsApp reachable.",
    },
    {
        "factor": "Email",
        "points": 4,
        "rule": "+4 if email found.",
    },
    {
        "factor": "Social profiles",
        "points": 3,
        "rule": "+3 if Instagram or Facebook profile exists.",
    },
    {
        "factor": "Core niche",
        "points": 6,
        "rule": "+6 for café / jeweller / clothing / shoes / multi-retail.",
    },
    {
        "factor": "City known",
        "points": 2,
        "rule": "+2 if city is filled.",
    },
]


def _platforms_list(lead: ShopLead) -> List[str]:
    raw = (lead.ad_platforms or "").lower().replace(";", ",").replace("|", ",")
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    # also infer from flags
    if lead.has_instagram_ads and "instagram" not in parts:
        parts.append("instagram")
    if lead.has_facebook_ads and "facebook" not in parts:
        parts.append("facebook")
    if lead.has_google_ads and "google" not in parts:
        parts.append("google")
    return parts


def compute_score_breakdown(lead: ShopLead) -> Tuple[int, List[Dict[str, Any]], str]:
    """
    Returns (total_score, factors_list, human_summary_string).
    factors_list: [{factor, points, detail}, ...]
    """
    factors: List[Dict[str, Any]] = []

    if lead.is_branded_chain is True:
        factors.append(
            {
                "factor": "Branded chain",
                "points": 0,
                "detail": "Excluded from ICP — score locked at 0",
            }
        )
        summary = "0 | Branded chain excluded"
        return 0, factors, summary

    total = 0

    def add(name: str, pts: int, detail: str) -> None:
        nonlocal total
        if pts == 0:
            return
        total += pts
        factors.append({"factor": name, "points": pts, "detail": detail})

    add("Base", 10, "Non-chain business baseline")

    if lead.is_independent is True:
        add("Independent shop", 15, "Family / boutique / independent signals")
    elif lead.is_independent is False:
        add("Not independent", -20, "Failed independence checks")

    pv = (lead.product_variety or "").lower()
    if pv == "high":
        add("Product variety high", 12, "Wide mix of products/kinds")
    elif pv == "medium":
        add("Product variety medium", 8, "Moderate assortment")

    if lead.carries_multiple_brands is True:
        add("Multi-brand inventory", 10, "Sells multiple brands / labels")

    # Website gap
    if lead.has_website is False or not lead.website:
        add("No website", 14, "Strong need for web presence")
        lead.has_website = False
        lead.website_quality = lead.website_quality or "none"
    else:
        wq = (lead.website_quality or "").lower()
        if wq in ("poor", "outdated", "none"):
            add("Poor / outdated website", 11, "Redesign + experience upgrade")
        elif wq == "average":
            add("Average website", 7, "Can still sell experience layers")
        elif wq == "good":
            add("Good website", 3, "Upsell catalogue/QR/booking still possible")

    # ---- ADS (high value) ----
    platforms = _platforms_list(lead)
    style = (lead.ad_style or "").lower().strip()
    topics = (lead.ad_topics or "").lower()
    runs = lead.runs_ads is True or bool(platforms) or bool(style)

    # Infer product style from topics if style missing
    product_topic_hits = [
        "product",
        "collection",
        "new arrival",
        "catalogue",
        "catalog",
        "menu",
        "jewellery",
        "jewelry",
        "gold",
        "dress",
        "shoes",
        "footwear",
        "outfit",
        "sku",
        "price",
        "buy now",
        "shop now",
        "lookbook",
        "bridal set",
        "ring",
        "necklace",
    ]
    offer_hits = ["offer", "sale", "discount", "festive", "promo", "% off", "deal"]
    if not style and topics:
        if any(h in topics for h in product_topic_hits):
            style = "product_showcase"
            lead.ad_style = style
        elif any(h in topics for h in offer_hits):
            style = "offer_promo"
            lead.ad_style = style

    if runs:
        lead.runs_ads = True
        add("Runs paid ads", 12, f"Platforms: {', '.join(platforms) or 'detected'}")

        if style in ("product_showcase", "product", "product_ads", "catalogue"):
            add(
                "PRODUCT advertising",
                20,
                f"Ads show products/collections — highest intent. Topics: {(lead.ad_topics or 'product focus')[:120]}",
            )
        elif style in ("offer_promo", "promo", "sale"):
            add("Offer / promo ads", 10, f"Sale/discount ads. Topics: {(lead.ad_topics or '')[:100]}")
        elif style in ("brand_awareness", "brand", "lifestyle"):
            add("Brand-awareness ads", 5, "Lifestyle/brand ads without hard product push")
        elif style in ("mixed",):
            add("Mixed ad style", 14, "Product + promo mix")
        else:
            # unknown but runs ads
            if any(h in topics for h in product_topic_hits):
                add("PRODUCT advertising (from topics)", 20, f"Topics: {topics[:120]}")
            elif topics:
                add("Ads with topics", 8, f"Topics: {topics[:120]}")

        if "instagram" in platforms or lead.has_instagram_ads:
            add("Instagram ads", 6, "Meta/Instagram paid or boost activity")
            lead.has_instagram_ads = True
        if "facebook" in platforms or lead.has_facebook_ads:
            add("Facebook ads", 4, "Facebook boosts / ads")
            lead.has_facebook_ads = True
        if "google" in platforms or lead.has_google_ads:
            add("Google ads", 4, "Google Search/Maps ads")
            lead.has_google_ads = True
        other = [p for p in platforms if p not in ("instagram", "facebook", "google", "meta")]
        if other:
            add("Other ad platforms", 3, ", ".join(other[:5]))

        # Conversion gap: ads without good website = gold for agency
        weak_web = (
            lead.has_website is False
            or not lead.website
            or (lead.website_quality or "").lower() in ("none", "poor", "outdated", "average")
        )
        if weak_web:
            add(
                "Ads + weak web conversion gap",
                10,
                "Spending on ads but no strong website to convert — premium agency fit",
            )

    # Contact
    if lead.phone or lead.whatsapp:
        add("Phone / WhatsApp", 8, lead.phone or lead.whatsapp or "reachable")
    if lead.email:
        add("Email", 4, lead.email)
    if lead.instagram or lead.facebook:
        add("Social profiles", 3, "Instagram/Facebook present")

    if lead.niche in ("cafe", "jeweller", "clothing", "shoes", "multi_retail"):
        add("Core niche", 6, f"Niche={lead.niche}")

    if lead.city:
        add("City known", 2, lead.city)

    total = max(0, min(100, total))
    # Build summary string for Sheets
    parts = [f"{f['factor']} {f['points']:+d}" for f in factors]
    summary = f"{total} | " + "; ".join(parts)
    return total, factors, summary


def apply_score(lead: ShopLead) -> ShopLead:
    """Mutates lead with score + breakdown fields."""
    total, factors, summary = compute_score_breakdown(lead)
    lead.lead_score = total
    lead.score_breakdown = summary
    # compact JSON-ish lines for sheets
    lead.score_factors = " || ".join(
        f"{f['factor']} ({f['points']:+d}): {f['detail']}" for f in factors
    )
    if lead.is_branded_chain:
        lead.status = "excluded_chain"
    return lead


def factors_table_for_lead(lead: ShopLead) -> List[Dict[str, Any]]:
    _, factors, _ = compute_score_breakdown(lead)
    return factors
