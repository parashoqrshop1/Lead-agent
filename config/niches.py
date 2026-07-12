"""
Ideal Customer Profile — INDEPENDENT shops only.

Agency sells websites + digital experience upgrades to:
  cafés, jewellers, clothing stores, shoe stores, multi-product retail,
  and similar independent / family-run shops that carry variety / mixed brands.

EXCLUDES: national/global branded chains, franchise flagships, pure brand mono-stores.
"""
from __future__ import annotations

from typing import Any, Dict, List

# ---- Primary niches the agency serves ----
NICHES: Dict[str, Dict[str, Any]] = {
    "cafe": {
        "label": "Café / Coffee shop / Bakery-café",
        "keywords": [
            "cafe",
            "café",
            "coffee shop",
            "coffee house",
            "bakery cafe",
            "tea house",
            "espresso bar",
            "independent coffee",
        ],
        "search_queries": [
            "independent cafe in {city}",
            "best local coffee shop {city} not chain",
            "family run cafe {city}",
            "artisan coffee {city}",
            "bakery cafe {city} contact",
        ],
        "must_have_signals": [
            "menu variety",
            "local vibe",
            "sit-in or takeaway",
            "independent ownership cues",
        ],
        "experience_pillars": [
            "digital menu + QR table ordering",
            "Instagram-to-website story",
            "online table reservation",
            "WhatsApp / Google reviews funnel",
            "loyalty stamp digital card",
            "event / live music calendar",
            "Google Business + Maps optimization",
        ],
        "offer_packages": [
            {
                "name": "Café Starter Site",
                "pitch": "Beautiful 1-page site with live menu, maps, WhatsApp order button",
            },
            {
                "name": "Café Experience Pro",
                "pitch": "QR menu, reservations, gallery, events, review booster",
            },
            {
                "name": "Café Growth Stack",
                "pitch": "Site + Google ads landing + Instagram shop link + loyalty page",
            },
        ],
    },
    "jeweller": {
        "label": "Independent jeweller / gold & silver shop",
        "keywords": [
            "jeweller",
            "jewelry store",
            "jewellery shop",
            "gold smith",
            "silver shop",
            "ornaments store",
            "local jeweller",
            "family jeweller",
        ],
        "search_queries": [
            "independent jewellery shop in {city}",
            "family gold jeweller {city}",
            "local silver ornaments store {city}",
            "custom jewellery maker {city}",
            "trusted local jeweller {city} not brand showroom",
        ],
        "must_have_signals": [
            "custom / made-to-order",
            "gold silver diamond mix",
            "local trust / family run",
            "variety of designs (not single brand mono)",
        ],
        "experience_pillars": [
            "catalogue of collections (bridal, daily wear, silver)",
            "appointment booking for try-on",
            "WhatsApp price enquiry (secure)",
            "trust badges + years in business story",
            "wedding season landing pages",
            "before/after custom work gallery",
            "Google Business with product photos",
        ],
        "offer_packages": [
            {
                "name": "Jeweller Trust Site",
                "pitch": "Elegant catalogue site highlighting craftsmanship & trust",
            },
            {
                "name": "Bridal Experience",
                "pitch": "Wedding collection pages + appointment booking + WhatsApp",
            },
            {
                "name": "Jeweller Omni",
                "pitch": "Full catalogue + enquiries + Maps + Instagram sync",
            },
        ],
    },
    "clothing": {
        "label": "Independent clothing / boutique / multi-brand apparel",
        "keywords": [
            "boutique",
            "clothing store",
            "garment shop",
            "fashion store",
            "apparel shop",
            "multi brand clothing",
            "mens wear shop",
            "ladies wear boutique",
            "ethnic wear store",
            "independent fashion retailer",
        ],
        "search_queries": [
            "independent clothing boutique {city}",
            "multi brand garment shop {city}",
            "family clothing store {city}",
            "ethnic wear boutique {city}",
            "mens ladies wear shop {city} not showroom chain",
        ],
        "must_have_signals": [
            "multiple brands or mixed variety",
            "independent / boutique (not mono-brand flagship)",
            "local retail storefront",
            "seasonal collections",
        ],
        "experience_pillars": [
            "lookbook / new arrivals",
            "category pages (men/women/kids/ethnic)",
            "WhatsApp size & availability check",
            "festival / sale campaign pages",
            "Instagram reels → shop page",
            "store locator + hours",
            "simple catalog or light e-commerce",
        ],
        "offer_packages": [
            {
                "name": "Boutique Lookbook",
                "pitch": "Visual site that feels like walking into the store",
            },
            {
                "name": "Retail Catalog",
                "pitch": "Categories + enquiry cart via WhatsApp",
            },
            {
                "name": "Fashion Growth",
                "pitch": "Lookbook + sales landing pages + Google visibility",
            },
        ],
    },
    "shoes": {
        "label": "Independent shoe / footwear store",
        "keywords": [
            "shoe store",
            "footwear shop",
            "shoe shop",
            "sneakers store independent",
            "multi brand footwear",
            "family shoe store",
        ],
        "search_queries": [
            "independent shoe store {city}",
            "multi brand footwear shop {city}",
            "family shoe shop {city}",
            "local sneakers and formal shoes {city}",
        ],
        "must_have_signals": [
            "variety of footwear styles/brands",
            "independent retailer",
            "not pure brand mono-store (Nike-only flagship etc.)",
        ],
        "experience_pillars": [
            "category grid (formal, sports, kids, heels)",
            "size-guide page",
            "WhatsApp stock check",
            "seasonal sale pages",
            "store photos + fitting experience story",
            "Maps + parking notes",
        ],
        "offer_packages": [
            {
                "name": "Footwear Window",
                "pitch": "Clean product-window site for walk-in + WhatsApp sales",
            },
            {
                "name": "Shoe Retail Pro",
                "pitch": "Categories, size guide, offers, Maps, Instagram bridge",
            },
        ],
    },
    "multi_retail": {
        "label": "Independent multi-product / general / variety retail",
        "keywords": [
            "general store",
            "variety store",
            "department store local",
            "multi product shop",
            "family retail store",
            "kirana with variety",
            "gift and variety shop",
            "home and lifestyle store independent",
        ],
        "search_queries": [
            "independent variety store {city}",
            "family multi product shop {city}",
            "local general merchandise store {city}",
            "independent home lifestyle shop {city}",
        ],
        "must_have_signals": [
            "many product kinds / departments",
            "independent ownership",
            "local neighborhood store",
        ],
        "experience_pillars": [
            "department-wise navigation",
            "weekly offers page",
            "WhatsApp order list",
            "delivery radius page",
            "loyalty / membership page",
            "Google Business posts automation guide",
        ],
        "offer_packages": [
            {
                "name": "Neighborhood Hub Site",
                "pitch": "Simple site so locals find hours, offers, WhatsApp orders",
            },
            {
                "name": "Retail Command",
                "pitch": "Departments + offers + Maps + enquiry funnel",
            },
        ],
    },
    "other_independent": {
        "label": "Other independent specialty shops",
        "keywords": [
            "independent shop",
            "family business store",
            "local specialty retailer",
            "artisan shop",
        ],
        "search_queries": [
            "independent specialty shop {city}",
            "family run retail store {city}",
        ],
        "must_have_signals": ["independent", "local"],
        "experience_pillars": [
            "brand story",
            "product highlights",
            "contact + WhatsApp",
            "Google visibility",
        ],
        "offer_packages": [
            {
                "name": "Independent Shop Site",
                "pitch": "Story-led website that makes a small shop feel premium",
            }
        ],
    },
}

# Chains / brands to DOWN-SCORE or exclude (not exhaustive — agent also uses LLM judgment)
BRANDED_CHAIN_BLOCKLIST = [
    # Global coffee / QSR
    "starbucks",
    "costa coffee",
    "dunkin",
    "mcdonald",
    "kfc",
    "subway",
    "domino",
    "pizza hut",
    "burger king",
    "tim hortons",
    "cafe coffee day",
    "ccd ",
    "barista coffee",
    "third wave coffee chain",
    # Fashion mono / big retail chains
    "zara",
    "h&m",
    "h and m",
    "uniqlo",
    "forever 21",
    "gap ",
    "old navy",
    "mango store",
    "bershka",
    "pull&bear",
    "massimo dutti",
    "nike store",
    "adidas store",
    "puma store",
    "skechers",
    "crocs store",
    "reebok store",
    "levi's exclusive",
    "levis exclusive",
    "us polo exclusive",
    "tommy hilfiger",
    "calvin klein",
    "mark & spencer",
    "marks and spencer",
    "westside",
    "pantaloons",
    "lifestyle stores",
    "shoppers stop",
    "reliance trends",
    "reliance digital",
    "max fashion",
    "ajio store",
    "myntra",
    # Jewellery big brands / chains
    "tanishq",
    "kalyan jewellers",
    "malabar gold",
    "joyalukkas",
    "pcj ",
    "png jewellers chain",
    "senco gold",
    "reliance jewels",
    "caratlane store",
    "bluestone store",
    # Footwear chains
    "metro shoes",
    "inc.5",
    "bata store",
    "bata ",
    "relaxo",
    "khadim",
    "stevemadden",
    "charles & keith",
    "aldo store",
    # Hyper / supermarket chains
    "walmart",
    "target ",
    "costco",
    "tesco",
    "sainsbury",
    "dmart",
    "d-mart",
    "big bazaar",
    "reliance fresh",
    "reliance smart",
    "more megastore",
    "spencer's",
    "nature's basket",
]

INDEPENDENT_POSITIVE_SIGNALS = [
    "family run",
    "family-owned",
    "family owned",
    "since 19",
    "since 20",
    "est.",
    "established",
    "local favourite",
    "local favorite",
    "home grown",
    "homegrown",
    "artisan",
    "handcrafted",
    "custom made",
    "made to order",
    "multi brand",
    "multibrand",
    "multi-brand",
    "various brands",
    "wide variety",
    "independent",
    "proprietor",
    "owner operated",
    "boutique",
    "not a chain",
]

# Regions
REGIONS = {
    "india": {
        "label": "🇮🇳 India",
        "country": "India",
        "cities": [
            "Delhi",
            "Mumbai",
            "Bangalore",
            "Hyderabad",
            "Chennai",
            "Kolkata",
            "Pune",
            "Ahmedabad",
            "Jaipur",
            "Lucknow",
            "Kanpur",
            "Akbarpur",
            "Varanasi",
            "Noida",
            "Gurgaon",
            "Indore",
            "Chandigarh",
            "Surat",
            "Nagpur",
            "Patna",
        ],
    },
    "us": {
        "label": "🇺🇸 United States",
        "country": "United States",
        "cities": [
            "New York",
            "Los Angeles",
            "Chicago",
            "Houston",
            "Phoenix",
            "Philadelphia",
            "San Antonio",
            "San Diego",
            "Dallas",
            "Austin",
            "Miami",
            "Seattle",
            "Denver",
            "Atlanta",
            "Boston",
            "Portland",
            "Nashville",
        ],
    },
    "other_english": {
        "label": "🌍 Other English (UK/CA/AU/NZ/AE/SG)",
        "country": "International",
        "cities": [
            "London",
            "Manchester",
            "Birmingham",
            "Toronto",
            "Vancouver",
            "Sydney",
            "Melbourne",
            "Auckland",
            "Dubai",
            "Singapore",
            "Dublin",
            "Cape Town",
        ],
    },
}


def list_niche_options() -> List[dict]:
    return [{"id": k, "label": v["label"]} for k, v in NICHES.items()]


def niche_label(niche_id: str) -> str:
    return NICHES.get(niche_id, {}).get("label", niche_id)


def experience_for(niche_id: str) -> List[str]:
    return list(NICHES.get(niche_id, {}).get("experience_pillars", []))


def packages_for(niche_id: str) -> List[dict]:
    return list(NICHES.get(niche_id, {}).get("offer_packages", []))


def search_queries_for(niche_id: str, city: str) -> List[str]:
    niche = NICHES.get(niche_id) or NICHES["other_independent"]
    return [q.format(city=city) for q in niche.get("search_queries", [])]
