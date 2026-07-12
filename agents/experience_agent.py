"""
Experience Agent — designs digital-experience offers for independent shops.

Works fully FREE with templates (no LLM). Optionally upgrades copy with Gemini.
"""
from __future__ import annotations

from typing import List, Optional

from agents.lead_schema import ExperienceProposal, ShopLead, utc_now
from agents.storage import save_proposal, update_lead
from config.niches import experience_for, niche_label, packages_for
from config.settings import get_settings


def _pick_package(lead: ShopLead) -> dict:
    packages = packages_for(lead.niche or "other_independent")
    if not packages:
        return {
            "name": "Independent Shop Experience",
            "pitch": "Modern web presence that feels premium and converts walk-ins + WhatsApp",
        }

    # No / poor site → starter; average → pro; good → growth/omni last package
    wq = (lead.website_quality or "none").lower()
    if not lead.website or wq in ("none", "poor"):
        return packages[0]
    if wq == "average" and len(packages) > 1:
        return packages[1]
    return packages[-1]


def _pillars_for(lead: ShopLead, limit: int = 5) -> List[str]:
    pillars = experience_for(lead.niche or "other_independent")
    # Personalize order: if no website, put foundation first
    if not lead.website:
        extra = [
            "foundational mobile website with clear offers",
            "click-to-WhatsApp / call buttons",
            "Google Business profile that matches the new brand story",
        ]
        pillars = extra + pillars
    return pillars[:limit]


def build_experience_proposal(lead: ShopLead, use_llm: bool = False) -> ExperienceProposal:
    s = get_settings()
    agency = s["agency_name"]
    website = s["agency_website"]
    tagline = s.get("agency_tagline") or "Digital experiences for independent shops"
    niche = niche_label(lead.niche or "other_independent")
    package = _pick_package(lead)
    pillars = _pillars_for(lead)

    name = lead.business_name or "your shop"
    city = lead.city or "your city"

    if not lead.website or (lead.website_quality or "") in ("none", "poor"):
        gap = (
            f"{name} is an independent {niche.lower()} in {city} with a weak or missing "
            f"web presence — customers who search online may never find you."
        )
    else:
        gap = (
            f"{name} already has a site, but independent shops win today with experience "
            f"layers: catalogues, booking, WhatsApp commerce, and a branded story — not just a homepage."
        )

    variety_note = ""
    if lead.carries_multiple_brands or (lead.product_variety or "").lower() == "high":
        variety_note = (
            " Your multi-brand / high-variety inventory is perfect for a digital lookbook "
            "or smart catalogue that showcases range without looking like a chain."
        )

    headline = f"{package['name']} for {name}"
    summary = (
        f"{gap}{variety_note}\n\n"
        f"Recommended package: **{package['name']}** — {package['pitch']}.\n"
        f"Built by {agency} ({tagline})."
    )

    # Optional free Gemini rewrite
    if use_llm:
        rewritten = _llm_polish(name, city, niche, package, pillars, summary)
        if rewritten:
            summary = rewritten.get("summary", summary)
            headline = rewritten.get("headline", headline)
            if rewritten.get("pillars"):
                pillars = rewritten["pillars"]

    niche_short = {
        "cafe": "cafés",
        "jeweller": "jewellers",
        "clothing": "clothing boutiques",
        "shoes": "shoe stores",
        "multi_retail": "multi-product shops",
    }.get(lead.niche or "", "independent shops")

    wa = (
        f"Hi! I work with local {niche_short} (not big chains).\n\n"
        f"I looked at *{name}* in {city}. "
        f"{'You deserve a site that matches the quality of your shop.' if not lead.website else 'Your online experience can convert more walk-ins & WhatsApp chats.'}\n\n"
        f"We built a package called *{package['name']}*: {package['pitch']}.\n\n"
        f"Want a free 5-min digital experience idea for {name}? "
        f"No obligation.\n\n— {agency}\n{website}"
    )

    email = (
        f"Subject: A digital experience idea for {name}\n\n"
        f"Hi{(' ' + lead.owner_name) if lead.owner_name else ''},\n\n"
        f"We help independent cafés, jewellers, clothing & shoe stores, and multi-product "
        f"retailers look and sell better online — without making them feel like a chain.\n\n"
        f"{summary}\n\n"
        f"Experience pillars we recommend:\n"
        + "\n".join(f"• {p}" for p in pillars)
        + f"\n\nHappy to share a free mini-audit for {name}.\n\n"
        f"Best regards,\n{agency}\n{s['agency_email']}\n{website}\n{s['agency_whatsapp']}"
    )

    prop = ExperienceProposal(
        lead_id=lead.id,
        business_name=name,
        niche=lead.niche,
        package_name=package["name"],
        headline=headline,
        summary=summary,
        pillars=pillars,
        outreach_whatsapp=wa,
        outreach_email=email,
        created_at=utc_now(),
    )

    # Update lead fields
    update_lead(
        lead.id,
        experience_fit=summary[:500],
        recommended_package=package["name"],
        status="experience_pitched" if lead.status in ("new", "qualified", "enriching") else lead.status,
    )
    save_proposal(prop)
    return prop


def _llm_polish(
    name: str,
    city: str,
    niche: str,
    package: dict,
    pillars: List[str],
    summary: str,
) -> Optional[dict]:
    """Optional free Gemini polish — fails soft if no key / package missing."""
    try:
        s = get_settings()
        if not s.get("llm_api_key"):
            return None
        import google.generativeai as genai

        genai.configure(api_key=s["llm_api_key"])
        model_name = s["llm_model"].split("/")[-1]
        model = genai.GenerativeModel(model_name)
        prompt = f"""
Rewrite a short sales proposal for an independent shop digital-experience agency.
Shop: {name}, City: {city}, Niche: {niche}
Package: {package}
Pillars: {pillars}
Base summary: {summary}

Return pure JSON with keys: headline, summary, pillars (array of 4-6 short strings).
Tone: warm, premium, local, never corporate-chain. No markdown fences.
"""
        resp = model.generate_content(prompt)
        text = (resp.text or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()
        import json

        return json.loads(text)
    except Exception:
        return None


def draft_quick_outreach(lead: ShopLead) -> str:
    """Fast WhatsApp blurb without saving a full proposal."""
    prop = build_experience_proposal(lead, use_llm=False)
    return prop.outreach_whatsapp
