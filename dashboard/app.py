"""
Lead Agent — single-file Streamlit app (Cloud-safe).
No heavy imports at module load. Demo works offline. Real mode uses Gemini REST via httpx.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

st.set_page_config(page_title="Lead Agent", page_icon="🏪", layout="centered")

DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
LEADS_FILE = DATA / "leads.json"


# ---------------- models / storage (stdlib only) ----------------

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


@dataclass
class Lead:
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    business_name: str = ""
    niche: str = ""
    city: str = ""
    country: str = "India"
    phone: str = ""
    whatsapp: str = ""
    email: str = ""
    website: str = ""
    instagram: str = ""
    facebook: str = ""
    has_website: bool = False
    website_quality: str = "none"
    is_independent: bool = True
    is_branded_chain: bool = False
    product_variety: str = "high"
    carries_multiple_brands: bool = True
    runs_ads: bool = False
    ad_platforms: str = ""
    ad_topics: str = ""
    ad_style: str = ""
    pain_points: str = ""
    notes: str = ""
    status: str = "new"
    lead_score: int = 0
    score_breakdown: str = ""
    source_url: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def score(self) -> int:
        if self.is_branded_chain:
            self.lead_score = 0
            self.score_breakdown = "0 | chain excluded"
            return 0
        s = 10
        parts = ["Base +10"]
        if self.is_independent:
            s += 15
            parts.append("Independent +15")
        if self.product_variety == "high":
            s += 12
            parts.append("Variety +12")
        if self.carries_multiple_brands:
            s += 10
            parts.append("Multi-brand +10")
        if not self.has_website or not self.website:
            s += 14
            parts.append("No website +14")
            self.has_website = False
            self.website_quality = "none"
        if self.runs_ads:
            s += 12
            parts.append("Paid ads +12")
        if (self.ad_style or "").startswith("product"):
            s += 20
            parts.append("PRODUCT ads/posts +20")
        elif self.instagram or self.facebook:
            s += 12
            parts.append("Social product/social +12")
        if self.instagram:
            s += 10
            parts.append("Instagram +10")
        elif self.facebook:
            s += 8
            parts.append("Facebook +8")
        if self.phone or self.whatsapp:
            s += 8
            parts.append("Phone +8")
        if self.niche in ("cafe", "jeweller", "clothing", "shoes", "multi_retail"):
            s += 6
            parts.append("Niche +6")
        if self.city:
            s += 2
            parts.append("City +2")
        if (self.instagram or self.facebook) and not self.website:
            s += 8
            parts.append("Marketing intent +8")
        self.lead_score = max(0, min(100, s))
        self.score_breakdown = f"{self.lead_score} | " + "; ".join(parts)
        return self.lead_score


def _secret(key: str, default: str = "") -> str:
    try:
        v = st.secrets.get(key, None)
        if v is not None and str(v).strip():
            return str(v).strip()
    except Exception:
        pass
    import os

    return (os.getenv(key) or default).strip()


def load_leads() -> List[Lead]:
    if not LEADS_FILE.exists():
        return []
    try:
        raw = json.loads(LEADS_FILE.read_text(encoding="utf-8") or "[]")
    except Exception:
        return []
    out: List[Lead] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        known = {f.name for f in Lead.__dataclass_fields__.values()}  # type: ignore
        kwargs = {k: v for k, v in item.items() if k in known}
        try:
            lead = Lead(**kwargs)
            lead.score()
            out.append(lead)
        except Exception:
            continue
    return out


def save_leads(leads: List[Lead]) -> None:
    LEADS_FILE.write_text(
        json.dumps([asdict(l) for l in leads], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _norm_phone(p: str) -> str:
    d = re.sub(r"\D+", "", p or "")
    return d[-10:] if len(d) >= 10 else d


def _core_name(n: str) -> str:
    t = re.sub(r"\([^)]*\)", " ", (n or "").lower())
    t = re.split(r"\s*[-–—]\s*", t)[0]
    return re.sub(r"\s+", " ", t).strip()


def upsert(leads: List[Lead], new_leads: List[Lead]) -> tuple[List[Lead], int, int]:
    by: Dict[str, Lead] = {}
    order: List[str] = []

    def keys(l: Lead) -> List[str]:
        ks = []
        ph = _norm_phone(l.phone or l.whatsapp)
        if ph and len(ph) >= 8:
            ks.append(f"p:{ph}")
        name = _core_name(l.business_name)
        city = (l.city or "").lower().strip()
        if name and city:
            ks.append(f"n:{name}|{city}")
        if l.instagram and "example" not in l.instagram:
            ks.append(f"ig:{(l.instagram or '').lower()}")
        if not ks:
            ks.append(f"id:{l.id}")
        return ks

    def add_one(l: Lead) -> str:
        l.score()
        ks = keys(l)
        for k in ks:
            if k in by:
                old = by[k]
                # merge
                d = asdict(old)
                for kk, vv in asdict(l).items():
                    if kk in ("id", "created_at"):
                        continue
                    if vv in (None, "", False) and d.get(kk) not in (None, ""):
                        continue
                    if kk == "lead_score":
                        d[kk] = max(int(d.get(kk) or 0), int(vv or 0))
                    elif vv not in (None, ""):
                        d[kk] = vv
                m = Lead(**d)
                m.score()
                by[k] = m
                for nk in keys(m):
                    by[nk] = m
                return "u"
        by_id = l.id
        for k in ks:
            by[k] = l
        order.append(by_id)
        by[f"id:{by_id}"] = l
        return "a"

    # seed with existing unique
    for l in leads:
        add_one(l)
    # rebuild order from unique objects
    seen_obj = set()
    uniq: List[Lead] = []
    for l in list(by.values()):
        if id(l) in seen_obj:
            continue
        seen_obj.add(id(l))
        uniq.append(l)

    # simpler merge approach: dict by phone or name|city
    merged: Dict[str, Lead] = {}
    for l in leads + new_leads:
        l.score()
        ph = _norm_phone(l.phone or l.whatsapp)
        key = f"p:{ph}" if ph and len(ph) >= 8 else f"n:{_core_name(l.business_name)}|{(l.city or '').lower()}"
        if key in merged:
            old = merged[key]
            d = asdict(old)
            for kk, vv in asdict(l).items():
                if kk in ("id", "created_at"):
                    continue
                if vv not in (None, "", [], {}):
                    if kk == "lead_score":
                        d[kk] = max(int(d.get(kk) or 0), int(vv or 0))
                    else:
                        d[kk] = vv
            m = Lead(**d)
            m.updated_at = utc_now()
            m.score()
            merged[key] = m
        else:
            merged[key] = l
    out = list(merged.values())
    out.sort(key=lambda x: x.lead_score, reverse=True)
    save_leads(out)
    return out, len(new_leads), 0


# ---------------- demo + real generators ----------------

NICHES = {
    "cafe": "Café / coffee",
    "jeweller": "Jeweller",
    "clothing": "Clothing / boutique",
    "shoes": "Shoes / footwear",
    "multi_retail": "Multi-product retail",
}

LOCALITIES = {
    "Akbarpur": [
        "Main Market",
        "Sadar Bazar",
        "Station Road",
        "Katra",
        "Purani Bazar",
        "Bus Stand",
        "Tanda Road",
        "Tehsil Road",
    ],
    "Lucknow": ["Hazratganj", "Aminabad", "Chowk", "Alambagh", "Gomti Nagar", "Indira Nagar"],
    "Kanpur": ["Pared", "Birhana Road", "Mall Road", "Govind Nagar", "Kakadeo"],
    "Jaipur": ["Johari Bazar", "Bapu Bazar", "Raja Park", "Malviya Nagar"],
    "Ayodhya": ["Civil Lines", "Saket", "Station Road", "Main Market"],
    "Varanasi": ["Godowlia", "Sigra", "Lanka", "Maidagin"],
}


def localities(city: str) -> List[str]:
    areas = LOCALITIES.get(city) or [
        "Main Market",
        "Sadar Bazar",
        "Station Road",
        "Civil Lines",
        "Old City",
        "Bus Stand",
    ]
    return [city] + [f"{city} {a}" for a in areas]


def make_demo_leads(city: str, niches: List[str], limit: int = 40) -> List[Lead]:
    templates = {
        "cafe": [
            ("Chai Corner", True, "product_showcase", "menu reels, latte posts", True),
            ("Roast House Café", True, "offer_promo", "happy hour boosts", False),
            ("Filter Coffee Point", False, "", "instagram only menu photos", False),
            ("Bake & Brew Local", True, "product_showcase", "cakes product ads", True),
        ],
        "jeweller": [
            ("Shree Local Jewellers", True, "product_showcase", "bridal sets reels", False),
            ("Silver Oak Ornaments", True, "product_showcase", "oxidised jewellery ads", False),
            ("Family Gold House", False, "", "whatsapp catalogue only", False),
            ("Mangalam Gems", True, "product_showcase", "new collection IG ads", True),
        ],
        "clothing": [
            ("Thread Boutique", True, "product_showcase", "new arrivals lookbook", False),
            ("Cotton Street Wear", True, "offer_promo", "festival sale ads", False),
            ("Style Chowk Multi Brand", True, "product_showcase", "ethnic + western reels", False),
            ("Urban Weave Garments", True, "product_showcase", "product ads weak site", True),
        ],
        "shoes": [
            ("Sole Brothers Footwear", True, "product_showcase", "sneakers product posts", False),
            ("StepLocal Shoes", False, "", "facebook page products", False),
            ("Footprint Multi Brand", True, "product_showcase", "IG product ads", False),
        ],
        "multi_retail": [
            ("Mehta Variety Store", True, "product_showcase", "weekly product drops", False),
            ("Neighbourhood Hub Mart", False, "", "whatsapp order list", False),
            ("City Needs General", True, "mixed", "fb + ig products", False),
        ],
    }
    places = localities(city)
    out: List[Lead] = []
    n = 0
    for place in places:
        for niche in niches:
            for name, runs, style, topics, has_web in templates.get(niche, templates["clothing"]):
                if n >= limit:
                    break
                h = abs(hash(f"{name}|{place}|{niche}")) % 10_000_000
                lead = Lead(
                    business_name=f"{name} — {place}",
                    niche=niche,
                    city=city,
                    country="India",
                    phone=f"+91 98{h % 100000000:08d}"[:14],
                    whatsapp=f"+91 98{h % 100000000:08d}"[:14],
                    instagram=f"https://instagram.com/shop_{h}",
                    facebook=f"https://facebook.com/shop_{h}",
                    website=f"https://old-site-{h}.blogspot.com" if has_web else "",
                    has_website=has_web,
                    website_quality="poor" if has_web else "none",
                    runs_ads=runs,
                    ad_style=style or ("product_showcase" if not runs else ""),
                    ad_platforms="instagram, facebook" if runs else "instagram",
                    ad_topics=topics,
                    pain_points=f"Local {NICHES.get(niche, niche)} in {place}; social product showcase; website gap",
                    notes=f"locality:{place} | social-first independent shop",
                    source_url="demo://local",
                    is_independent=True,
                    product_variety="high",
                    carries_multiple_brands=True,
                )
                lead.score()
                out.append(lead)
                n += 1
            if n >= limit:
                break
        if n >= limit:
            break
    return out


def gemini_json(prompt: str, api_key: str, model: str = "gemini-2.0-flash") -> Any:
    import httpx

    model = (model or "gemini-2.0-flash").replace("google_genai/", "")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    with httpx.Client(timeout=60.0) as client:
        r = client.post(url, json=payload)
        if r.status_code == 404:
            url = url.replace(model, "gemini-1.5-flash")
            r = client.post(url, json=payload)
        if r.status_code >= 400:
            raise RuntimeError(f"Gemini {r.status_code}: {r.text[:300]}")
        data = r.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    return json.loads(text)


def fetch_text(url: str) -> str:
    import httpx

    with httpx.Client(
        timeout=25.0,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; LeadAgent/1.0)"},
    ) as client:
        r = client.get(url)
        r.raise_for_status()
        html = r.text
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html).strip()
    return html[:12000]


def real_hunt(city: str, niches: List[str], api_key: str, limit: int = 30) -> tuple[List[Lead], List[str]]:
    errors: List[str] = []
    leads: List[Lead] = []
    places = localities(city)[:6]
    for niche in niches:
        for place in places[:4]:
            q = f"independent {NICHES.get(niche, niche)} Instagram {place}"
            url = f"https://www.bing.com/search?q={quote_plus(q)}&count=20"
            try:
                page = fetch_text(url)
                prompt = f"""
Extract INDEPENDENT local {NICHES.get(niche, niche)} shops near {place}, India from this search text.
Prefer shops with Instagram/Facebook and product posts (ads or organic).
Exclude chains (Tanishq, Zara, Starbucks, Bata flagship, etc).
Return JSON: {{"leads":[{{"business_name":"","niche":"{niche}","city":"{city}","phone":"","whatsapp":"","email":"","website":"","instagram":"","facebook":"","has_website":false,"runs_ads":false,"ad_style":"product_showcase|offer_promo|","ad_topics":"","pain_points":"","notes":""}}]}}
Max 8 shops. Search text:
{page}
"""
                raw = gemini_json(prompt, api_key)
                items = raw.get("leads") if isinstance(raw, dict) else raw
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict) or not item.get("business_name"):
                        continue
                    lead = Lead(
                        business_name=str(item.get("business_name")),
                        niche=str(item.get("niche") or niche),
                        city=str(item.get("city") or city),
                        country="India",
                        phone=str(item.get("phone") or ""),
                        whatsapp=str(item.get("whatsapp") or ""),
                        email=str(item.get("email") or ""),
                        website=str(item.get("website") or ""),
                        instagram=str(item.get("instagram") or ""),
                        facebook=str(item.get("facebook") or ""),
                        has_website=bool(item.get("has_website") or item.get("website")),
                        runs_ads=bool(item.get("runs_ads")),
                        ad_style=str(item.get("ad_style") or ""),
                        ad_topics=str(item.get("ad_topics") or ""),
                        pain_points=str(item.get("pain_points") or ""),
                        notes=str(item.get("notes") or f"locality:{place}"),
                        source_url=f"bing:{q}",
                        is_independent=True,
                        product_variety="high",
                        carries_multiple_brands=True,
                    )
                    if not lead.website:
                        lead.has_website = False
                        lead.website_quality = "none"
                    lead.score()
                    leads.append(lead)
            except Exception as e:
                errors.append(f"{place}/{niche}: {e}")
            if len(leads) >= limit:
                break
        if len(leads) >= limit:
            break
    return leads[:limit], errors


def outreach(lead: Lead, agency: str, wa: str) -> str:
    return (
        f"Hi! I work with independent local shops (not big chains).\n\n"
        f"I found *{lead.business_name}* in {lead.city or 'your area'}. "
        f"You already showcase products on social"
        f"{' and run ads' if lead.runs_ads else ''}"
        f"{' but your website is weak/missing' if not lead.website else ''}.\n\n"
        f"We build simple websites + product showcase pages + WhatsApp enquiry for shops like yours.\n\n"
        f"Want a free 5-min idea for {lead.business_name}? No obligation.\n\n"
        f"— {agency}\n{wa}"
    )


# ---------------- UI ----------------

def css():
    st.markdown(
        """
        <style>
        .block-container{max-width:720px;padding-top:1rem}
        .card{border:1px solid #334155;border-radius:14px;padding:12px;margin:0 0 10px;background:#0f172a}
        .name{font-weight:700;color:#f8fafc}
        .meta{color:#94a3b8;font-size:.9rem}
        .pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:.75rem;font-weight:700;margin-right:6px}
        .hi{background:#14532d;color:#86efac}.mid{background:#713f12;color:#fde68a}.lo{background:#7f1d1d;color:#fecaca}
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    css()
    pwd = _secret("DASHBOARD_PASSWORD", "demo123")
    mode = (_secret("SCRAPER_MODE", "demo") or "demo").lower()
    gemini = _secret("GEMINI_API_KEY", "")
    agency = _secret("AGENCY_NAME", "Your Web Agency")
    wa = _secret("AGENCY_WHATSAPP", "")
    model = _secret("LLM_MODEL", "gemini-2.0-flash")

    if not st.session_state.get("auth"):
        st.title("🏪 Lead Agent")
        st.caption("Independent local shops · social + product showcase leads")
        with st.form("login"):
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Enter", type="primary", use_container_width=True):
                if (p or "").strip() == pwd:
                    st.session_state["auth"] = True
                    st.rerun()
                st.error("Wrong password")
        st.caption("Default if unset: demo123")
        return

    st.title("🏪 Lead Agent")
    real_ready = mode in ("light", "real", "gemini_web") and bool(gemini)
    if real_ready:
        st.success(f"Mode: **REAL/light** · Gemini key present")
    else:
        st.error(
            f"Mode: **{mode or 'demo'}** (test/sample). "
            "For REAL leads set Secrets: SCRAPER_MODE=\"light\" + GEMINI_API_KEY then Reboot."
        )

    nav = st.radio("Menu", ["Home", "Find leads", "Leads", "Settings"], horizontal=True, label_visibility="collapsed")
    leads = [l for l in load_leads() if not l.is_branded_chain]

    if nav == "Home":
        c1, c2, c3 = st.columns(3)
        c1.metric("Leads", len(leads))
        c2.metric("Score ≥70", sum(1 for l in leads if l.lead_score >= 70))
        c3.metric("With social", sum(1 for l in leads if l.instagram or l.facebook))

        if st.button("⚡ Generate leads NOW", type="primary", use_container_width=True):
            with st.spinner("Generating…"):
                errs: List[str] = []
                new: List[Lead] = []
                if real_ready:
                    try:
                        new, errs = real_hunt(
                            "Akbarpur",
                            ["jeweller", "clothing", "cafe", "shoes", "multi_retail"],
                            gemini,
                            limit=40,
                        )
                    except Exception as e:
                        errs.append(str(e))
                    if not new:
                        st.warning("Real hunt returned 0 — loading local samples so you're not stuck.")
                        new = make_demo_leads("Akbarpur", ["jeweller", "clothing", "cafe", "shoes"], 50)
                        errs.append("Fell back to samples because real hunt empty/failed.")
                else:
                    new = make_demo_leads("Akbarpur", ["jeweller", "clothing", "cafe", "shoes", "multi_retail"], 50)
                all_leads, _, _ = upsert(load_leads(), new)
                st.success(f"Saved {len(all_leads)} total leads (added batch {len(new)})")
                for e in errs[:5]:
                    st.warning(e)
                st.session_state["show_table"] = True
                st.rerun()

        if leads:
            st.markdown("#### Top leads")
            for l in sorted(leads, key=lambda x: x.lead_score, reverse=True)[:8]:
                pill = "hi" if l.lead_score >= 70 else "mid" if l.lead_score >= 45 else "lo"
                st.markdown(
                    f'<div class="card"><div class="name">{l.business_name}</div>'
                    f'<div class="meta">{l.niche} · {l.city} · {l.phone or "no phone"}</div>'
                    f'<span class="pill {pill}">{l.lead_score}/100</span>'
                    f'<div class="meta">IG: {l.instagram or "—"}</div></div>',
                    unsafe_allow_html=True,
                )

    elif nav == "Find leads":
        city = st.selectbox(
            "City / town",
            [
                "Akbarpur",
                "Ayodhya",
                "Lucknow",
                "Kanpur",
                "Varanasi",
                "Jaipur",
                "Sultanpur",
                "Tanda",
                "Other…",
            ],
        )
        if city == "Other…":
            city = st.text_input("Type city", value="Akbarpur")
        niches = st.multiselect(
            "Niches",
            list(NICHES.keys()),
            default=["jeweller", "clothing", "cafe", "shoes", "multi_retail"],
            format_func=lambda x: NICHES[x],
        )
        limit = st.slider("Target leads", 20, 100, 50)
        if st.button("📍 Hunt local niche leads", type="primary", use_container_width=True):
            with st.spinner(f"Hunting in {city}…"):
                errs: List[str] = []
                new: List[Lead] = []
                if real_ready:
                    try:
                        new, errs = real_hunt(city, niches or ["clothing"], gemini, limit=limit)
                    except Exception as e:
                        errs = [str(e)]
                    tag = "REAL"
                    if not new:
                        st.warning("Real hunt empty/failed — using samples so you still get output.")
                        new = make_demo_leads(city, niches or ["clothing"], limit)
                        tag = "FALLBACK SAMPLES"
                else:
                    new = make_demo_leads(city, niches or ["clothing"], limit)
                    tag = "DEMO"
                all_leads, _, _ = upsert(load_leads(), new)
                st.success(f"[{tag}] batch {len(new)} · total stored {len(all_leads)}")
                for e in errs[:8]:
                    st.warning(e)
                # immediate table
                rows = [
                    {
                        "score": l.lead_score,
                        "name": l.business_name,
                        "city": l.city,
                        "phone": l.phone,
                        "instagram": l.instagram,
                        "ads": l.ad_style,
                        "niche": l.niche,
                    }
                    for l in sorted(all_leads, key=lambda x: x.lead_score, reverse=True)[:60]
                ]
                st.dataframe(rows, use_container_width=True)
                st.download_button(
                    "⬇️ Download CSV",
                    data=("score,name,city,phone,instagram,facebook,website,niche,ads,breakdown\n"
                          + "\n".join(
                              f"\"{l.lead_score}\",\"{l.business_name}\",\"{l.city}\",\"{l.phone}\","
                              f"\"{l.instagram}\",\"{l.facebook}\",\"{l.website}\",\"{l.niche}\","
                              f"\"{l.ad_style}\",\"{l.score_breakdown}\""
                              for l in all_leads
                          )),
                    file_name="leads.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

        st.markdown("### Go REAL")
        st.code(
            'SCRAPER_MODE = "light"\n'
            'GEMINI_API_KEY = "your_key_from_aistudio.google.com"\n'
            'DASHBOARD_PASSWORD = "your-password"\n'
            'AGENCY_NAME = "Your Web Agency"',
            language="toml",
        )

    elif nav == "Leads":
        if not leads:
            st.warning("No leads yet. Go to Find leads / Generate now.")
        else:
            q = st.text_input("Search")
            min_score = st.select_slider("Min score", [0, 40, 60, 70, 80, 90], value=0)
            only_social = st.toggle("Only Instagram/Facebook", False)
            filtered = []
            for l in leads:
                if l.lead_score < min_score:
                    continue
                if only_social and not (l.instagram or l.facebook):
                    continue
                blob = f"{l.business_name} {l.city} {l.phone} {l.niche}".lower()
                if q and q.lower() not in blob:
                    continue
                filtered.append(l)
            filtered.sort(key=lambda x: x.lead_score, reverse=True)
            labels = [f"{l.lead_score} · {l.business_name}" for l in filtered]
            if not labels:
                st.info("No matches")
            else:
                choice = st.selectbox("Pick lead", labels)
                lead = filtered[labels.index(choice)]
                st.markdown(
                    f"**{lead.business_name}**  \n"
                    f"Score: **{lead.lead_score}**  \n"
                    f"📞 {lead.phone or lead.whatsapp or '—'}  \n"
                    f"📷 {lead.instagram or '—'}  \n"
                    f"👤 {lead.facebook or '—'}  \n"
                    f"🌐 {lead.website or 'no website'}  \n"
                    f"📣 {lead.ad_style or '—'} · {lead.ad_topics or '—'}  \n"
                    f"Pain: {lead.pain_points or '—'}  \n"
                    f"`{lead.score_breakdown}`"
                )
                st.text_area("WhatsApp pitch", outreach(lead, agency, wa), height=180)
                status = st.selectbox(
                    "Status",
                    ["new", "qualified", "contacted", "meeting", "won", "lost"],
                    index=0,
                )
                if st.button("Save status", use_container_width=True):
                    all_leads = load_leads()
                    for i, l in enumerate(all_leads):
                        if l.id == lead.id:
                            all_leads[i].status = status
                            all_leads[i].updated_at = utc_now()
                    save_leads(all_leads)
                    st.success("Saved")
                if st.button("Delete lead", use_container_width=True):
                    save_leads([l for l in load_leads() if l.id != lead.id])
                    st.rerun()

        if st.button("Clear ALL leads", use_container_width=True):
            save_leads([])
            st.rerun()

    else:
        st.write("### Settings")
        st.json(
            {
                "mode": mode,
                "gemini_key": bool(gemini),
                "real_ready": real_ready,
                "agency": agency,
                "leads_file": str(LEADS_FILE),
                "stored_leads": len(leads),
            }
        )
        st.markdown(
            """
**REAL secrets**
```toml
SCRAPER_MODE = "light"
GEMINI_API_KEY = "..."
LLM_MODEL = "gemini-2.0-flash"
DASHBOARD_PASSWORD = "..."
```
"""
        )
        if st.button("Log out", use_container_width=True):
            st.session_state.clear()
            st.rerun()


if __name__ == "__main__":
    main()
