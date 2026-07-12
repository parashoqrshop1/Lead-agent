"""
Lead Agent — single-file Streamlit app.
REAL mode never invents phones/IG. Demo samples are clearly labeled [SAMPLE].
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
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
    product_variety: str = "medium"
    carries_multiple_brands: bool = False
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
    is_sample: bool = False  # True only for practice samples
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
        if (self.product_variety or "") == "high":
            s += 12
            parts.append("Variety +12")
        if self.carries_multiple_brands:
            s += 10
            parts.append("Multi-brand +10")
        if not self.has_website or not self.website:
            s += 14
            parts.append("No website +14")
            self.has_website = False
            self.website_quality = self.website_quality or "none"
        if self.runs_ads:
            s += 12
            parts.append("Paid ads +12")
        if (self.ad_style or "").startswith("product"):
            s += 20
            parts.append("PRODUCT posts/ads +20")
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
    known = set(Lead.__dataclass_fields__.keys())
    for item in raw:
        if not isinstance(item, dict):
            continue
        kwargs = {k: v for k, v in item.items() if k in known}
        try:
            lead = Lead(**kwargs)
            # mark obvious old fakes
            if (
                lead.source_url.startswith("demo://")
                or "shop_" in (lead.instagram or "")
                or "[SAMPLE]" in (lead.business_name or "")
            ):
                lead.is_sample = True
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
    t = re.sub(r"\[[^\]]*\]", " ", (n or "").lower())
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.split(r"\s*[-–—]\s*", t)[0]
    return re.sub(r"\s+", " ", t).strip()


def upsert(existing: List[Lead], new_leads: List[Lead]) -> List[Lead]:
    merged: Dict[str, Lead] = {}
    for l in existing + new_leads:
        l.score()
        ph = _norm_phone(l.phone or l.whatsapp)
        if ph and len(ph) >= 8:
            key = f"p:{ph}"
        else:
            key = f"n:{_core_name(l.business_name)}|{(l.city or '').lower()}"
        if key in merged:
            old = merged[key]
            d = asdict(old)
            for kk, vv in asdict(l).items():
                if kk in ("id", "created_at"):
                    continue
                if vv not in (None, "", [], {}):
                    if kk == "lead_score":
                        d[kk] = max(int(d.get(kk) or 0), int(vv or 0))
                    elif kk == "is_sample":
                        # real wins over sample
                        d[kk] = bool(d.get(kk)) and bool(vv)
                    else:
                        d[kk] = vv
            m = Lead(**d)
            m.updated_at = utc_now()
            m.score()
            merged[key] = m
        else:
            merged[key] = l
    out = list(merged.values())
    out.sort(key=lambda x: (0 if x.is_sample else 1, x.lead_score), reverse=True)
    save_leads(out)
    return out


NICHES = {
    "cafe": "Café / coffee",
    "jeweller": "Jeweller",
    "clothing": "Clothing / boutique",
    "shoes": "Shoes / footwear",
    "multi_retail": "Multi-product retail",
}

LOCALITIES = {
    "Akbarpur": ["Main Market", "Sadar Bazar", "Station Road", "Katra", "Bus Stand", "Tanda Road"],
    "Indore": ["Rajwada", "Sarafa", "MG Road", "Vijay Nagar", "Palasia", "Bhawarkua"],
    "Lucknow": ["Hazratganj", "Aminabad", "Chowk", "Alambagh", "Gomti Nagar"],
    "Kanpur": ["Pared", "Birhana Road", "Mall Road", "Govind Nagar"],
    "Jaipur": ["Johari Bazar", "Bapu Bazar", "Raja Park"],
    "Ayodhya": ["Civil Lines", "Station Road", "Main Market"],
    "Varanasi": ["Godowlia", "Sigra", "Lanka"],
}


def locality_list(city: str) -> List[str]:
    areas = LOCALITIES.get(city) or ["Main Market", "Sadar Bazar", "Station Road", "Civil Lines"]
    return [city] + [f"{city} {a}" for a in areas]


def make_demo_leads(city: str, niches: List[str], limit: int = 20) -> List[Lead]:
    """Practice data only — clearly labeled, NO fake phone/IG that looks real."""
    templates = {
        "cafe": ["Practice Café A", "Practice Coffee House B"],
        "jeweller": ["Practice Jewellers A", "Practice Gold Shop B"],
        "clothing": ["Practice Boutique A", "Practice Garments B"],
        "shoes": ["Practice Footwear A"],
        "multi_retail": ["Practice Variety Store A"],
    }
    out: List[Lead] = []
    n = 0
    for niche in niches:
        for name in templates.get(niche, ["Practice Shop"]):
            if n >= limit:
                break
            lead = Lead(
                business_name=f"[SAMPLE] {name} ({city})",
                niche=niche,
                city=city,
                country="India",
                phone="",  # never fake phone
                whatsapp="",
                instagram="",  # never fake IG
                facebook="",
                website="",
                has_website=False,
                runs_ads=False,
                ad_style="product_showcase",
                ad_topics="sample only — not a real shop",
                pain_points="THIS IS FAKE PRACTICE DATA. Use REAL mode with Gemini for real shops.",
                notes="SAMPLE ONLY — not a real business",
                source_url="sample://practice",
                is_sample=True,
                is_independent=True,
                product_variety="high",
                carries_multiple_brands=True,
            )
            lead.score()
            out.append(lead)
            n += 1
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
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
    }
    with httpx.Client(timeout=75.0) as client:
        r = client.post(url, json=payload)
        if r.status_code == 404:
            url2 = url.replace(model, "gemini-1.5-flash")
            r = client.post(url2, json=payload)
        if r.status_code == 429:
            raise RuntimeError(
                "GEMINI QUOTA EXCEEDED (429). Free daily/minute limit hit. "
                "Wait 1–24 hours OR create a new free API key at https://aistudio.google.com/apikey "
                "OR enable billing. NO fake leads will be invented."
            )
        if r.status_code >= 400:
            raise RuntimeError(f"Gemini API {r.status_code}: {r.text[:350]}")
        data = r.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        raise RuntimeError(f"Bad Gemini response: {data}") from e
    text = (text or "").strip()
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
        headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/122 Mobile Safari/537.36"
        },
    ) as client:
        r = client.get(url)
        r.raise_for_status()
        html = r.text
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html).strip()
    return html[:14000]


def real_hunt(
    city: str,
    niches: List[str],
    api_key: str,
    model: str,
    limit: int = 25,
) -> Tuple[List[Lead], List[str]]:
    """
    REAL only. Few Gemini calls to save free quota.
    Never invents phone/IG — only what model extracts from public search text.
    """
    errors: List[str] = []
    leads: List[Lead] = []
    places = locality_list(city)[:5]

    # ONE call per niche (not per locality) to reduce quota burn
    for niche in niches:
        place_blob = ", ".join(places)
        # gather public search snippets for a few queries
        snippets = []
        queries = [
            f"{NICHES.get(niche, niche)} shop {city} contact Instagram",
            f"best independent {NICHES.get(niche, niche)} in {city} Facebook",
            f"{NICHES.get(niche, niche)} {city} Main Market Instagram",
            f"{NICHES.get(niche, niche)} near {city} WhatsApp number",
        ]
        for q in queries[:3]:
            url = f"https://www.bing.com/search?q={quote_plus(q)}&count=20"
            try:
                snippets.append(f"QUERY: {q}\n{fetch_text(url)[:3500]}")
            except Exception as e:
                errors.append(f"search fetch failed: {q}: {e}")

        if not snippets:
            errors.append(f"{niche}: no search pages fetched")
            continue

        prompt = f"""
You extract REAL independent local businesses from public search result text.

City/town: {city}, India
Niche: {NICHES.get(niche, niche)}
Also consider nearby markets: {place_blob}

RULES:
1) ONLY include businesses that appear in the search text (do not invent names).
2) Do NOT invent phone numbers or Instagram handles.
3) If phone/IG/website is not clearly present, leave it as empty string "".
4) Exclude national chains (Tanishq, Kalyan, Zara, H&M, Starbucks, Bata mono-store, Reliance Trends, etc.).
5) Prefer shops that seem local/independent and have social or product mentions.
6) Return up to 10 shops.

Return JSON only:
{{
  "leads": [
    {{
      "business_name": "exact name from text",
      "niche": "{niche}",
      "city": "{city}",
      "address": "",
      "phone": "",
      "whatsapp": "",
      "email": "",
      "website": "",
      "instagram": "",
      "facebook": "",
      "has_website": false,
      "runs_ads": false,
      "ad_style": "",
      "ad_topics": "",
      "pain_points": "",
      "notes": "short evidence quote from search text"
    }}
  ]
}}

SEARCH TEXT:
{chr(10).join(snippets)[:11000]}
"""
        try:
            raw = gemini_json(prompt, api_key, model=model)
        except Exception as e:
            errors.append(f"{niche}: {e}")
            # stop further niches if quota exceeded
            if "429" in str(e) or "QUOTA" in str(e).upper():
                break
            continue

        items = raw.get("leads") if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            errors.append(f"{niche}: model returned no leads list")
            continue

        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("business_name") or "").strip()
            if not name or name.lower() in ("n/a", "none", "unknown"):
                continue
            # reject obviously invented pattern handles
            ig = str(item.get("instagram") or "").strip()
            fb = str(item.get("facebook") or "").strip()
            phone = str(item.get("phone") or item.get("whatsapp") or "").strip()
            if re.fullmatch(r"https?://instagram\.com/shop_\d+", ig or ""):
                ig = ""
            if re.fullmatch(r"https?://facebook\.com/shop_\d+", fb or ""):
                fb = ""

            lead = Lead(
                business_name=name,
                niche=str(item.get("niche") or niche),
                city=str(item.get("city") or city),
                country="India",
                phone=phone,
                whatsapp=str(item.get("whatsapp") or phone or ""),
                email=str(item.get("email") or ""),
                website=str(item.get("website") or ""),
                instagram=ig,
                facebook=fb,
                has_website=bool(item.get("website")),
                runs_ads=bool(item.get("runs_ads")),
                ad_style=str(item.get("ad_style") or ""),
                ad_topics=str(item.get("ad_topics") or ""),
                pain_points=str(item.get("pain_points") or ""),
                notes=str(item.get("notes") or item.get("address") or ""),
                source_url=f"real:{city}:{niche}",
                is_sample=False,
                is_independent=True,
                product_variety="medium",
                carries_multiple_brands=False,
            )
            if not lead.website:
                lead.has_website = False
                lead.website_quality = "none"
            # if social product style unknown but social exists, keep empty (honest)
            lead.score()
            leads.append(lead)

        if len(leads) >= limit:
            break

    # de-dupe within batch
    uniq: Dict[str, Lead] = {}
    for l in leads:
        k = f"{_core_name(l.business_name)}|{(l.city or '').lower()}"
        if k not in uniq:
            uniq[k] = l
    return list(uniq.values())[:limit], errors


def outreach(lead: Lead, agency: str, wa: str) -> str:
    if lead.is_sample:
        return "This is SAMPLE data — do not message. Run REAL hunt with Gemini quota available."
    return (
        f"Hi! I help independent local shops (not chains) with websites & product showcase pages.\n\n"
        f"I came across *{lead.business_name}* in {lead.city or 'your area'}. "
        f"{'You already use social to show products' if (lead.instagram or lead.facebook) else 'Your shop looks like a strong local brand'}"
        f"{' and your website is missing/weak' if not lead.website else ''}.\n\n"
        f"Would you like a free 5-min idea to get more enquiries online?\n\n"
        f"— {agency}\n{wa}"
    )


def css() -> None:
    st.markdown(
        """
        <style>
        .block-container{max-width:740px;padding-top:1rem}
        .card{border:1px solid #334155;border-radius:14px;padding:12px;margin:0 0 10px;background:#0f172a}
        .name{font-weight:700;color:#f8fafc}
        .meta{color:#94a3b8;font-size:.9rem}
        .pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:.75rem;font-weight:700;margin-right:6px}
        .hi{background:#14532d;color:#86efac}.mid{background:#713f12;color:#fde68a}
        .lo{background:#7f1d1d;color:#fecaca}.sam{background:#4c1d95;color:#ddd6fe}
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
    real_ready = mode in ("light", "real", "gemini_web") and bool(gemini)

    if not st.session_state.get("auth"):
        st.title("🏪 Lead Agent")
        with st.form("login"):
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Enter", type="primary", use_container_width=True):
                if (p or "").strip() == pwd:
                    st.session_state["auth"] = True
                    st.rerun()
                st.error("Wrong password")
        return

    st.title("🏪 Lead Agent")
    if real_ready:
        st.success("Mode: **REAL** (Gemini key loaded). No fake numbers will be invented.")
    else:
        st.error(
            "Mode: **NOT REAL yet**. Set Secrets then Reboot:\n\n"
            '`SCRAPER_MODE = "light"`\n'
            '`GEMINI_API_KEY = "your_key"`'
        )

    # auto-clean old fakes once
    if not st.session_state.get("cleaned_fakes"):
        cur = load_leads()
        real_only = [
            l
            for l in cur
            if not l.is_sample
            and not (l.source_url or "").startswith("demo://")
            and not (l.source_url or "").startswith("sample://")
            and "shop_" not in (l.instagram or "")
            and "[SAMPLE]" not in (l.business_name or "")
        ]
        if len(real_only) != len(cur):
            save_leads(real_only)
            st.warning(f"Removed {len(cur) - len(real_only)} old fake/sample leads from storage.")
        st.session_state["cleaned_fakes"] = True

    nav = st.radio(
        "Menu",
        ["Home", "Find REAL leads", "Leads", "Settings"],
        horizontal=True,
        label_visibility="collapsed",
    )
    leads = [l for l in load_leads() if not l.is_branded_chain]
    real_leads = [l for l in leads if not l.is_sample]
    sample_leads = [l for l in leads if l.is_sample]

    if nav == "Home":
        c1, c2, c3 = st.columns(3)
        c1.metric("REAL leads", len(real_leads))
        c2.metric("Samples", len(sample_leads))
        c3.metric("With phone", sum(1 for l in real_leads if l.phone or l.whatsapp))

        if st.button("🗑 Delete ALL stored leads (including fakes)", use_container_width=True):
            save_leads([])
            st.session_state["cleaned_fakes"] = True
            st.success("Cleared.")
            st.rerun()

        st.markdown("#### Top REAL leads")
        if not real_leads:
            st.info("No REAL leads yet. Open **Find REAL leads**.")
        for l in sorted(real_leads, key=lambda x: x.lead_score, reverse=True)[:10]:
            st.markdown(
                f'<div class="card"><div class="name">{l.business_name}</div>'
                f'<div class="meta">{l.niche} · {l.city} · 📞 {l.phone or "not found publicly"}</div>'
                f'<div class="meta">IG: {l.instagram or "—"} · FB: {l.facebook or "—"}</div>'
                f'<span class="pill hi">{l.lead_score}/100</span></div>',
                unsafe_allow_html=True,
            )

    elif nav == "Find REAL leads":
        st.markdown("### Hunt real shops")
        city = st.selectbox(
            "City / town",
            [
                "Akbarpur",
                "Indore",
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
            city = st.text_input("Type city", "Akbarpur")
        niches = st.multiselect(
            "Niches",
            list(NICHES.keys()),
            default=["jeweller", "clothing", "cafe"],
            format_func=lambda x: NICHES[x],
        )
        limit = st.slider("Max leads to extract", 10, 40, 20)
        only_real = st.toggle("REAL only (never add samples)", value=True)

        if st.button("📍 Hunt REAL local leads", type="primary", use_container_width=True):
            if not real_ready:
                st.error(
                    "REAL mode not configured.\n\n"
                    "Streamlit Secrets must be:\n"
                    'SCRAPER_MODE = "light"\n'
                    'GEMINI_API_KEY = "your_key"\n'
                    "Then Reboot the app."
                )
            elif not niches:
                st.error("Pick at least one niche")
            else:
                with st.spinner(
                    "Calling public search + Gemini (uses free quota — few calls)…"
                ):
                    try:
                        new, errs = real_hunt(
                            city, niches, gemini, model=model, limit=limit
                        )
                    except Exception as e:
                        new, errs = [], [str(e)]

                    if errs:
                        for e in errs[:10]:
                            st.error(e)

                    if not new:
                        st.error(
                            "0 REAL leads found.\n\n"
                            "Common reasons:\n"
                            "1) Gemini free quota exceeded (429) — wait or new API key\n"
                            "2) Invalid GEMINI_API_KEY\n"
                            "3) Search pages blocked / empty\n"
                            "4) Model found no independent shops in text\n\n"
                            "NO fake shops were added."
                        )
                        if not only_real:
                            st.warning("Samples disabled by default. Turn off REAL only to load labeled samples.")
                    else:
                        all_leads = upsert(load_leads(), new)
                        st.success(
                            f"REAL batch: {len(new)} · total stored: {len(all_leads)} "
                            f"(real: {sum(1 for l in all_leads if not l.is_sample)})"
                        )
                        rows = [
                            {
                                "score": l.lead_score,
                                "name": l.business_name,
                                "city": l.city,
                                "phone": l.phone or "(not public)",
                                "instagram": l.instagram or "(not public)",
                                "facebook": l.facebook or "(not public)",
                                "website": l.website or "(none)",
                                "notes": (l.notes or "")[:80],
                            }
                            for l in sorted(new, key=lambda x: x.lead_score, reverse=True)
                        ]
                        st.dataframe(rows, use_container_width=True)
                        st.download_button(
                            "⬇️ Download REAL CSV",
                            data=(
                                "score,name,city,phone,instagram,facebook,website,niche,notes\n"
                                + "\n".join(
                                    f"\"{l.lead_score}\",\"{l.business_name}\",\"{l.city}\","
                                    f"\"{l.phone}\",\"{l.instagram}\",\"{l.facebook}\","
                                    f"\"{l.website}\",\"{l.niche}\",\"{(l.notes or '').replace('\"','')}\""
                                    for l in all_leads
                                    if not l.is_sample
                                )
                            ),
                            file_name=f"real_leads_{city}.csv",
                            mime="text/csv",
                            use_container_width=True,
                        )

        with st.expander("Optional: load clearly labeled SAMPLE data (for UI practice only)"):
            if st.button("Load [SAMPLE] practice rows"):
                samples = make_demo_leads(city if city != "Other…" else "Akbarpur", niches or ["clothing"], 10)
                upsert(load_leads(), samples)
                st.warning("Added SAMPLE rows only — names start with [SAMPLE], no fake phones.")
                st.rerun()

        st.markdown("### Fix Gemini quota (your screenshot error)")
        st.markdown(
            """
Your log showed **`Gemini 429 — exceeded current quota`**.

That means free Gemini limit is finished for now. When that happens:
- ❌ old app invented fake shops (wrong — now fixed)
- ✅ new app stops and tells you honestly

**What to do:**
1. Open https://aistudio.google.com/apikey  
2. Create a **new** API key (or wait until quota resets — often next day)  
3. Paste into Streamlit Secrets as `GEMINI_API_KEY`  
4. Reboot app  
5. Hunt again with fewer niches first (1 niche, limit 15)
"""
        )

    elif nav == "Leads":
        show = st.radio("Show", ["REAL only", "All", "Samples only"], horizontal=True)
        if show == "REAL only":
            view = real_leads
        elif show == "Samples only":
            view = sample_leads
        else:
            view = leads
        if not view:
            st.warning("No leads in this filter.")
        else:
            labels = [
                f"{'[SAMPLE] ' if l.is_sample else ''}{l.lead_score} · {l.business_name}"
                for l in sorted(view, key=lambda x: x.lead_score, reverse=True)
            ]
            choice = st.selectbox("Pick", labels)
            lead = sorted(view, key=lambda x: x.lead_score, reverse=True)[labels.index(choice)]
            if lead.is_sample:
                st.error("SAMPLE DATA — not a real shop. Do not call/message.")
            st.write(f"**{lead.business_name}**")
            st.write(f"Score: {lead.lead_score}")
            st.write(f"📞 Phone: {lead.phone or lead.whatsapp or '(not found publicly)'}")
            st.write(f"📷 Instagram: {lead.instagram or '(not found publicly)'}")
            st.write(f"👤 Facebook: {lead.facebook or '(not found publicly)'}")
            st.write(f"🌐 Website: {lead.website or '(none)'}")
            st.write(f"Notes: {lead.notes or '—'}")
            st.caption(lead.score_breakdown)
            st.text_area("WhatsApp draft", outreach(lead, agency, wa), height=160)
            if st.button("Delete this lead", use_container_width=True):
                save_leads([l for l in load_leads() if l.id != lead.id])
                st.rerun()

        if st.button("🗑 Clear ALL leads", use_container_width=True):
            save_leads([])
            st.rerun()

    else:
        st.write("### Settings / status")
        st.json(
            {
                "mode": mode,
                "gemini_key_present": bool(gemini),
                "real_ready": real_ready,
                "model": model,
                "real_leads": len(real_leads),
                "sample_leads": len(sample_leads),
            }
        )
        st.code(
            'SCRAPER_MODE = "light"\n'
            'GEMINI_API_KEY = "YOUR_KEY"\n'
            'LLM_MODEL = "gemini-2.0-flash"\n'
            'DASHBOARD_PASSWORD = "your-password"\n'
            'AGENCY_NAME = "Your Web Agency"\n'
            'AGENCY_WHATSAPP = "+91XXXXXXXXXX"',
            language="toml",
        )
        if st.button("Log out", use_container_width=True):
            st.session_state.clear()
            st.rerun()


if __name__ == "__main__":
    main()
