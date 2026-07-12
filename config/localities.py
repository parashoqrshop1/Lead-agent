"""
Local market areas for high-volume niche discovery.

Big-city-only searches miss most independent shops.
We sweep city + market / road / colony localities.
"""
from __future__ import annotations

from typing import Dict, List

# Common Indian market patterns (applied when city has no custom list)
GENERIC_INDIA_AREAS = [
    "Main Market",
    "Sadar Bazar",
    "Station Road",
    "Civil Lines",
    "Old City",
    "Naya Bazar",
    "Chaurahe",
    "Bus Stand Market",
    "GT Road",
    "Near Railway Station",
]

# City-specific localities (UP + major India markets for the agency)
CITY_LOCALITIES: Dict[str, List[str]] = {
    "Akbarpur": [
        "Main Market",
        "Sadar Bazar",
        "Station Road",
        "Katra",
        "Purani Bazar",
        "Naya Bazar",
        "Tehsil Road",
        "Bus Stand",
        "Ashrafpur Kichhauchha Road",
        "Tanda Road",
        "Baskhari Road",
        "Jalalpur Road",
    ],
    "Lucknow": [
        "Hazratganj",
        "Aminabad",
        "Chowk",
        "Alambagh",
        "Gomti Nagar",
        "Indira Nagar",
        "Aliganj",
        "Rajajipuram",
        "Ashiyana",
        "LDA Colony",
        "Kapoorthala",
        "Nishatganj",
        "Thakurganj",
        "Charbagh",
        "Mahanagar",
    ],
    "Kanpur": [
        "Pared",
        "Birhana Road",
        "Mall Road",
        "Swaroop Nagar",
        "Kakadeo",
        "Govind Nagar",
        "Kidwai Nagar",
        "Barra",
        "Kalyanpur",
        "Rawatpur",
        "Gumti No 5",
        "Naveen Market",
    ],
    "Varanasi": [
        "Godowlia",
        "Lahurabir",
        "Lanka",
        "Sigra",
        "Maidagin",
        "Chetganj",
        "Bhelupur",
        "Orderly Bazar",
        "Luxa",
        "Pandeypur",
    ],
    "Jaipur": [
        "Johari Bazar",
        "Bapu Bazar",
        "Chandpole",
        "Raja Park",
        "Malviya Nagar",
        "Vaishali Nagar",
        "C Scheme",
        "Tonk Road",
        "Mansarovar",
        "Pink City",
    ],
    "Pune": [
        "Laxmi Road",
        "FC Road",
        "JM Road",
        "Camp",
        "Kothrud",
        "Hadapsar",
        "Baner",
        "Aundh",
        "Deccan",
        "Swargate",
    ],
    "Delhi": [
        "Chandni Chowk",
        "Karol Bagh",
        "Lajpat Nagar",
        "Sarojini Nagar",
        "Connaught Place",
        "Rohini",
        "Dwarka",
        "Saket",
        "Janakpuri",
        "Shahdara",
    ],
    "Mumbai": [
        "Dadar",
        "Andheri",
        "Borivali",
        "Bandra",
        "Thane",
        "Crawford Market",
        "Linking Road",
        "Colaba",
        "Ghatkopar",
        "Powai",
    ],
    "Noida": [
        "Sector 18",
        "Sector 62",
        "Atta Market",
        "Gaur City",
        "Greater Noida",
        "Sector 50",
    ],
    "Gurgaon": [
        "Sector 14",
        "MG Road",
        "DLF Phase 1",
        "Sohna Road",
        "Old Gurgaon",
        "Sector 56",
    ],
    "Ayodhya": [
        "Ram Ki Paidi",
        "Saket",
        "Civil Lines",
        "Railway Station Road",
        "Main Market",
    ],
    "Faizabad": [
        "Chowk",
        "Civil Lines",
        "Station Road",
        "Main Market",
        "Rekabganj",
    ],
    "Sultanpur": [
        "Main Market",
        "Station Road",
        "Civil Lines",
        "Sadar Bazar",
    ],
    "Ambedkar Nagar": [
        "Akbarpur Main Market",
        "Tanda",
        "Jalalpur",
        "Baskhari",
    ],
}

# Extra tier-2/3 India towns often missed by city-only scrapers
EXTRA_INDIA_CITIES = [
    "Akbarpur",
    "Ayodhya",
    "Faizabad",
    "Sultanpur",
    "Ambedkar Nagar",
    "Tanda",
    "Azamgarh",
    "Gorakhpur",
    "Prayagraj",
    "Bareilly",
    "Moradabad",
    "Aligarh",
    "Meerut",
    "Ghaziabad",
    "Agra",
    "Mathura",
    "Jhansi",
    "Gwalior",
    "Bhopal",
    "Raipur",
    "Ranchi",
    "Patna",
    "Muzaffarpur",
    "Dehradun",
    "Haridwar",
    "Ludhiana",
    "Amritsar",
    "Jalandhar",
    "Kota",
    "Udaipur",
    "Jodhpur",
    "Bhubaneswar",
    "Cuttack",
    "Guwahati",
    "Siliguri",
    "Coimbatore",
    "Madurai",
    "Trichy",
    "Mysore",
    "Mangalore",
    "Nashik",
    "Nagpur",
    "Aurangabad",
    "Vadodara",
    "Rajkot",
    "Surat",
    "Indore",
    "Ujjain",
]


def localities_for(city: str, max_areas: int = 8) -> List[str]:
    """Return market/area list for a city (includes city itself as first place)."""
    city_key = (city or "").strip()
    # try exact then title case
    areas = CITY_LOCALITIES.get(city_key) or CITY_LOCALITIES.get(city_key.title())
    if not areas:
        # heuristic for smaller Indian towns
        areas = list(GENERIC_INDIA_AREAS)
    places = [city_key] + [f"{city_key} {a}" for a in areas[: max(0, max_areas - 1)]]
    # unique preserve order
    seen = set()
    out = []
    for p in places:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out[:max_areas]


def social_niche_queries(niche_label: str, place: str) -> List[str]:
    """
    Queries that find shops WITH social presence (ads OR organic product posts).
    place can be city or city+locality.
    """
    n = niche_label
    p = place
    return [
        f"{n} Instagram {p}",
        f"{n} Facebook page {p}",
        f"independent {n} {p} Instagram",
        f"{n} shop {p} Instagram reels products",
        f"local {n} {p} WhatsApp order",
        f"{n} boutique {p} Instagram",
        f"best {n} near {p} Instagram",
        f"{n} {p} Facebook marketplace OR Instagram",
        f"family {n} {p} social media",
        f"{n} new arrivals Instagram {p}",
        f"{n} bridal collection Instagram {p}" if "jewel" in n.lower() else f"{n} new collection Instagram {p}",
        f"{n} menu Instagram {p}" if "café" in n.lower() or "cafe" in n.lower() or "coffee" in n.lower() else f"{n} catalogue Instagram {p}",
    ]


def marketing_intent_queries(niche_label: str, place: str) -> List[str]:
    """Shops that look ready for website / marketing help."""
    n = niche_label
    p = place
    return [
        f"{n} {p} no website Instagram only",
        f"{n} {p} WhatsApp business only",
        f"{n} shop {p} Google Business",
        f"local {n} {p} contact number Instagram",
        f"{n} {p} boost post OR sponsored Instagram",
        f"hire website for {n} {p}",
        f"{n} {p} online catalogue needed",
    ]
