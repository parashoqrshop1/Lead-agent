"""
Qualify Agent — free, no API required.

Filters branded chains, boosts independent multi-product shops,
and tags niches for the experience agency.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from agents.lead_schema import ShopLead
from config.niches import (
    BRANDED_CHAIN_BLOCKLIST,
    INDEPENDENT_POSITIVE_SIGNALS,
    NICHES,
)


def _norm(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def is_branded_chain_name(name: str, notes: str = "") -> bool:
    blob = _norm(f"{name} {notes}")
    for brand in BRANDED_CHAIN_BLOCKLIST:
        b = brand.lower().strip()
        if not b:
            continue
        # word-ish contains
        if b in blob:
            return True
    return False


def detect_independence(lead: ShopLead) -> Tuple[bool, bool, str]:
    """
    Returns (is_independent, is_branded_chain, signals_text)
    """
    blob = _norm(
        " ".join(
            [
                lead.business_name or "",
                lead.notes or "",
                lead.independence_signals or "",
                lead.category or "",
                lead.pain_points or "",
            ]
        )
    )

    if lead.is_branded_chain is True or is_branded_chain_name(
        lead.business_name or "", blob
    ):
        return False, True, "matched_brand_blocklist"

    signals = []
    for s in INDEPENDENT_POSITIVE_SIGNALS:
        if s in blob:
            signals.append(s)

    # Heuristics
    if lead.carries_multiple_brands is True:
        signals.append("multi-brand inventory")
    if (lead.product_variety or "").lower() == "high":
        signals.append("high product variety")
    if lead.instagram and not lead.website:
        signals.append("social-first independent retail pattern")

    # Default: assume independent unless proven chain
    is_chain = False
    is_indep = True if lead.is_independent is not False else False
    if signals:
        is_indep = True
    return is_indep, is_chain, ", ".join(signals) if signals else (lead.independence_signals or "assumed_independent")


def detect_niche(lead: ShopLead) -> str:
    if lead.niche and lead.niche in NICHES:
        return lead.niche
    blob = _norm(
        f"{lead.business_name} {lead.category} {lead.notes} {lead.pain_points}"
    )
    scores = {}
    for nid, meta in NICHES.items():
        score = 0
        for kw in meta.get("keywords", []):
            if kw.lower() in blob:
                score += 2
        scores[nid] = score
    best = max(scores, key=scores.get)
    if scores[best] <= 0:
        return lead.niche or "other_independent"
    return best


def qualify_lead(lead: ShopLead) -> ShopLead:
    is_indep, is_chain, signals = detect_independence(lead)
    lead.is_independent = is_indep
    lead.is_branded_chain = is_chain
    lead.independence_signals = signals
    lead.niche = detect_niche(lead)

    if is_chain:
        lead.status = "excluded_chain"
        lead.pain_points = lead.pain_points or "Branded chain — out of ICP"
        lead.experience_fit = "Excluded: agency focuses on independent shops only."
        lead.lead_score = 0
        return lead

    # Infer variety if missing
    if lead.carries_multiple_brands is None:
        blob = _norm(f"{lead.notes} {lead.independence_signals} {lead.category}")
        if any(x in blob for x in ("multi brand", "multi-brand", "multibrand", "various brands", "variety")):
            lead.carries_multiple_brands = True
            lead.product_variety = lead.product_variety or "high"

    if lead.has_website is None:
        lead.has_website = bool(lead.website)
    if not lead.website:
        lead.has_website = False
        lead.website_quality = lead.website_quality or "none"

    # Ads intelligence (heuristic, free) — product ads boost score heavily
    try:
        from agents.ads_agent import analyze_ads_heuristic

        lead = analyze_ads_heuristic(lead)
    except Exception:
        lead.recompute_score()

    if lead.lead_score >= 70 and lead.status in ("new", "enriching"):
        lead.status = "qualified"
    return lead


def qualify_batch(leads: List[ShopLead]) -> List[ShopLead]:
    return [qualify_lead(l) for l in leads]


def filter_icp(
    leads: List[ShopLead],
    *,
    drop_chains: bool = True,
    min_score: int = 0,
    niches: Optional[List[str]] = None,
) -> List[ShopLead]:
    out = []
    for l in leads:
        q = qualify_lead(l)
        if drop_chains and q.is_branded_chain:
            continue
        if q.lead_score < min_score:
            continue
        if niches and q.niche not in niches:
            continue
        out.append(q)
    return out
