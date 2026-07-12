"""
Independent Shop Lead Agent — mobile-first dashboard
FREE: Gemini light scrape + demo bulk + Sheets + scoring + ads intel
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from agents.ads_agent import analyze_ads_heuristic
from agents.experience_agent import build_experience_proposal, draft_quick_outreach
from agents.lead_schema import ShopLead
from agents.orchestrator import run_bulk_pipeline, run_full_pipeline, run_hyperlocal_pipeline
from agents.scraper_agent import health_check, search_leads, suggest_cities, suggest_niches
from agents.scoring import SCORE_FACTOR_GUIDE, factors_table_for_lead
from agents.sheets_store import push_leads_to_sheets, sheets_status
from agents.storage import (
    delete_lead,
    export_leads_excel,
    leads_dataframe,
    load_leads,
    purge_duplicate_leads,
    recent_activity,
    update_lead,
    upsert_leads,
)
from config.niches import REGIONS, niche_label
from config.settings import LEAD_STATUSES, get_settings

st.set_page_config(
    page_title="Lead Agent",
    page_icon="🏪",
    layout="centered",
    initial_sidebar_state="collapsed",
)


# ---------- auth ----------

def _read_dashboard_password() -> str:
    try:
        if hasattr(st, "secrets"):
            val = st.secrets.get("DASHBOARD_PASSWORD", None)
            if val is not None and str(val).strip() != "":
                return str(val).strip()
    except Exception:
        pass
    import os

    return (os.getenv("DASHBOARD_PASSWORD") or "change-me-now").strip() or "change-me-now"


def check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True
    expected = _read_dashboard_password()
    st.markdown("## 🔐 Lead Agent")
    st.caption("Independent shops · product-ad scoring · free stack")
    with st.form("login_form"):
        pwd = st.text_input("Password", type="password")
        ok = st.form_submit_button("Enter", type="primary", use_container_width=True)
    if ok:
        if (pwd or "").strip() == expected:
            st.session_state["authenticated"] = True
            st.rerun()
        st.error(f"Wrong password (typed {len((pwd or '').strip())} chars, expected {len(expected)})")
    if expected == "change-me-now":
        if st.button("Open with default password", use_container_width=True):
            st.session_state["authenticated"] = True
            st.rerun()
    return False


def inject_css():
    st.markdown(
        """
        <style>
        .block-container { padding-top: 0.8rem; padding-bottom: 5rem; max-width: 720px; }
        div[data-testid="stMetric"] {
            background: #111827; border: 1px solid #334155; border-radius: 14px;
            padding: 10px 12px;
        }
        div[data-testid="stMetric"] label { color: #94a3b8 !important; font-size: 0.8rem !important; }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: #f8fafc !important; font-size: 1.35rem !important;
        }
        .lead-card {
            border: 1px solid #334155; border-radius: 16px; padding: 14px 14px 10px;
            margin: 0 0 12px 0; background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
        }
        .lead-name { font-size: 1.05rem; font-weight: 700; color: #f8fafc; margin: 0 0 4px 0; }
        .lead-meta { color: #94a3b8; font-size: 0.9rem; margin: 0 0 8px 0; }
        .pill {
            display: inline-block; padding: 3px 10px; border-radius: 999px;
            font-size: 0.78rem; font-weight: 700; margin-right: 6px; margin-bottom: 4px;
        }
        .pill-hi { background: #14532d; color: #86efac; }
        .pill-mid { background: #713f12; color: #fde68a; }
        .pill-lo { background: #7f1d1d; color: #fecaca; }
        .pill-ad { background: #1e3a8a; color: #bfdbfe; }
        .pill-web { background: #334155; color: #e2e8f0; }
        .bottom-nav-spacer { height: 12px; }
        /* bigger touch targets */
        button[kind="primary"], button[kind="secondary"] { min-height: 2.7rem; }
        .stSelectbox, .stMultiSelect, .stTextInput, .stTextArea { margin-bottom: 0.2rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def score_pill(score: int) -> str:
    cls = "pill-hi" if score >= 70 else "pill-mid" if score >= 45 else "pill-lo"
    return f'<span class="pill {cls}">{score}/100</span>'


def lead_card_html(lead: ShopLead) -> str:
    ads = ""
    if lead.runs_ads:
        style = lead.ad_style or "ads"
        ads = f'<span class="pill pill-ad">📣 {style}</span>'
    web = "no website" if not lead.website else (lead.website_quality or "has site")
    return f"""
    <div class="lead-card">
      <div class="lead-name">{lead.business_name}</div>
      <div class="lead-meta">{niche_label(lead.niche or '')} · {lead.city or '—'} · {lead.phone or lead.whatsapp or 'no phone'}</div>
      {score_pill(lead.lead_score)}
      <span class="pill pill-web">{web}</span>
      {ads}
    </div>
    """


# ---------- pages ----------

def page_home():
    st.markdown("### 🏠 Home")
    df = leads_dataframe()
    h = health_check()
    total = 0 if df.empty else len(df)
    product_ads = 0
    high = 0
    if total:
        if "ad_style" in df:
            product_ads = int(
                df["ad_style"].fillna("").str.lower().isin(
                    ["product_showcase", "product", "mixed", "catalogue"]
                ).sum()
            )
        high = int((df["lead_score"] >= 70).sum())

    c1, c2, c3 = st.columns(3)
    c1.metric("Leads", total)
    c2.metric("Score ≥70", high)
    c3.metric("Product ads", product_ads)

    st.markdown("#### Quick actions")
    if st.button("📍 Hunt local niche shops", type="primary", use_container_width=True):
        st.session_state["nav"] = "Find leads"
        st.rerun()
    if st.button("📋 Open inbox", use_container_width=True):
        st.session_state["nav"] = "Leads"
        st.rerun()

    mode = h.get("scraper_mode")
    ready = h.get("ready")
    st.info(
        f"Mode: **{mode}** · Ready: **{'yes' if ready else 'no'}** · "
        f"Gemini key: **{'yes' if h.get('llm_key_present') else 'no'}**"
    )
    if mode == "demo":
        st.warning(
            "You are in **demo mode** (sample leads). "
            "For real shops: set `SCRAPER_MODE = \"light\"` + free `GEMINI_API_KEY` in Secrets. "
            "See **Go real** page."
        )

    st.markdown("#### Top leads")
    leads = sorted(load_leads(), key=lambda x: x.lead_score, reverse=True)
    leads = [l for l in leads if not l.is_branded_chain][:5]
    if not leads:
        st.caption("No leads yet — tap **Find more leads**.")
    for lead in leads:
        st.markdown(lead_card_html(lead), unsafe_allow_html=True)
        if st.button("Open", key=f"home_{lead.id}", use_container_width=True):
            st.session_state["selected_lead_id"] = lead.id
            st.session_state["nav"] = "Leads"
            st.rerun()


def page_leads():
    st.markdown("### 📋 Leads")
    leads = [l for l in load_leads() if not l.is_branded_chain]
    if not leads:
        st.warning("No leads yet.")
        if st.button("Find leads now", type="primary", use_container_width=True):
            st.session_state["nav"] = "Find leads"
            st.rerun()
        return

    # simple mobile filters
    q = st.text_input("Search name / city / phone", placeholder="e.g. Lucknow or jewellery")
    f1, f2 = st.columns(2)
    with f1:
        min_score = st.select_slider("Min score", options=[0, 40, 60, 70, 80, 90], value=0)
    with f2:
        only_product = st.toggle("Product ads only", value=False)

    filtered = []
    for l in leads:
        if l.lead_score < min_score:
            continue
        if only_product and (l.ad_style or "").lower() not in (
            "product_showcase",
            "product",
            "mixed",
            "catalogue",
        ):
            continue
        blob = f"{l.business_name} {l.city} {l.phone} {l.niche} {l.ad_topics}".lower()
        if q and q.lower() not in blob:
            continue
        filtered.append(l)
    filtered.sort(key=lambda x: x.lead_score, reverse=True)
    st.caption(f"{len(filtered)} leads")

    # choose lead with big labels (name not cryptic id)
    labels = {
        f"{l.lead_score} · {l.business_name} · {l.city or ''}": l.id for l in filtered
    }
    if not labels:
        st.info("No leads match filters.")
        return

    default_id = st.session_state.get("selected_lead_id")
    keys = list(labels.keys())
    default_idx = 0
    if default_id:
        for i, k in enumerate(keys):
            if labels[k] == default_id:
                default_idx = i
                break
    choice = st.selectbox("Pick a lead", keys, index=default_idx)
    lead_id = labels[choice]
    lead = next(l for l in filtered if l.id == lead_id)
    st.session_state["selected_lead_id"] = lead.id

    st.markdown(lead_card_html(lead), unsafe_allow_html=True)
    st.write(f"**Ads:** {lead.ad_platforms or '—'} · {lead.ad_topics or '—'}")
    st.write(f"**Pain:** {lead.pain_points or '—'}")

    with st.expander("Why this score?", expanded=False):
        factors = factors_table_for_lead(lead)
        if factors:
            st.dataframe(pd.DataFrame(factors), use_container_width=True, hide_index=True)
        st.caption(lead.score_breakdown or "")

    st.markdown("#### Actions")
    status = st.selectbox(
        "Status",
        LEAD_STATUSES,
        index=LEAD_STATUSES.index(lead.status) if lead.status in LEAD_STATUSES else 0,
    )
    notes = st.text_area("Notes", value=lead.notes or "", height=80)
    if st.button("💾 Save", type="primary", use_container_width=True):
        update_lead(lead.id, status=status, notes=notes)
        st.success("Saved")
        st.rerun()

    if st.button("✨ WhatsApp pitch", use_container_width=True):
        prop = build_experience_proposal(lead, use_llm=False)
        st.session_state["wa_draft"] = prop.outreach_whatsapp
        st.session_state["email_draft"] = prop.outreach_email
        st.success(prop.package_name)

    if "wa_draft" in st.session_state:
        st.text_area("Copy WhatsApp", value=st.session_state.get("wa_draft") or draft_quick_outreach(lead), height=180)
        st.text_area("Email draft", value=st.session_state.get("email_draft") or "", height=140)
    else:
        st.text_area("Quick WhatsApp", value=draft_quick_outreach(lead), height=160)

    b1, b2 = st.columns(2)
    with b1:
        if st.button("📣 Re-check ads", use_container_width=True):
            upsert_leads([analyze_ads_heuristic(lead)])
            st.rerun()
    with b2:
        if st.button("🗑 Delete", use_container_width=True):
            delete_lead(lead.id)
            st.session_state.pop("selected_lead_id", None)
            st.rerun()

    if st.button("🧹 Remove duplicate leads", use_container_width=True):
        result = purge_duplicate_leads()
        st.success(
            f"Cleaned: {result['before']} → {result['after']} "
            f"(removed {result['removed']} duplicates)"
        )
        st.rerun()

    st.download_button(
        "⬇️ Download CSV",
        data=leads_dataframe().to_csv(index=False).encode("utf-8"),
        file_name="leads.csv",
        mime="text/csv",
        use_container_width=True,
    )


def page_find():
    st.markdown("### ⚡ Find leads")
    h = health_check()
    st.caption(f"Mode: `{h['scraper_mode']}` · Gemini: {'✅' if h['llm_key_present'] else '❌'}")

    tab_local, tab_bulk, tab_one, tab_real = st.tabs(
        ["📍 Local niches", "🔥 Multi-city bulk", "🎯 One run", "🚀 Go real"]
    )

    with tab_local:
        st.markdown(
            """
**Dedicated niche hunt in your town / city markets**  
Finds independent shops that already use **Instagram / Facebook**  
(paid ads **or** organic product posts) — ideal for website + product showcase.
"""
        )
        region = st.selectbox(
            "Region",
            list(REGIONS.keys()),
            format_func=lambda x: REGIONS[x]["label"],
            key="loc_region",
        )
        city_opts = suggest_cities(region)
        # put smaller towns first if present
        default_city = "Akbarpur" if "Akbarpur" in city_opts else city_opts[0]
        city = st.selectbox(
            "City / town",
            city_opts + ["Other…"],
            index=(city_opts + ["Other…"]).index(default_city)
            if default_city in city_opts
            else 0,
            key="loc_city",
        )
        if city == "Other…":
            city = st.text_input("Type town / city", value="Akbarpur", key="loc_city_custom")

        niche_opts = suggest_niches()
        niche_ids = [n["id"] for n in niche_opts if n["id"] != "other_independent"]
        niches = st.multiselect(
            "Niches to hunt",
            niche_ids,
            default=["cafe", "jeweller", "clothing", "shoes", "multi_retail"],
            format_func=lambda i: next(n["label"] for n in niche_opts if n["id"] == i),
            key="loc_niches",
        )
        limit = st.slider("Target leads (unique)", 20, 120, 50, key="loc_limit")
        deep = st.toggle("Scan local markets / roads (recommended)", value=True)
        areas = st.slider("Max localities per city", 3, 12, 8, key="loc_areas")

        st.caption(
            "Examples scanned: Main Market, Station Road, Sadar Bazar, Civil Lines… "
            "plus Instagram/Facebook product-shop queries."
        )
        if st.button("📍 Hunt local niche leads", type="primary", use_container_width=True):
            if not city or not niches:
                st.error("Pick city and at least one niche")
            else:
                with st.spinner(f"Hunting {', '.join(niches)} around {city}…"):
                    try:
                        result = run_hyperlocal_pipeline(
                            region=region,
                            city=city,
                            niches=niches,
                            limit=limit,
                            deep_local=deep,
                            max_localities=areas,
                            analyze_ads=True,
                            drop_chains=True,
                            sync_sheets=True,
                        )
                        st.success(result["summary"])
                        if result.get("errors"):
                            for e in result["errors"][:5]:
                                st.caption(f"• {e}")
                        st.session_state["nav"] = "Leads"
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    with tab_bulk:
        st.write("Generate many leads across cities × niches in one tap.")
        region = st.selectbox(
            "Region",
            list(REGIONS.keys()),
            format_func=lambda x: REGIONS[x]["label"],
            key="bulk_region",
        )
        city_opts = suggest_cities(region)
        cities = st.multiselect(
            "Cities",
            city_opts,
            default=[c for c in ["Lucknow", "Kanpur", "Akbarpur", "Jaipur", "Pune"] if c in city_opts][:4]
            or city_opts[:3],
        )
        niche_opts = suggest_niches()
        niche_ids = [n["id"] for n in niche_opts if n["id"] != "other_independent"]
        niches = st.multiselect(
            "Niches",
            niche_ids,
            default=["cafe", "jeweller", "clothing", "shoes"],
            format_func=lambda i: next(n["label"] for n in niche_opts if n["id"] == i),
        )
        per = st.slider("Leads per city×niche", 10, 40, 20)
        if st.button("🚀 Run bulk find", type="primary", use_container_width=True):
            if not cities or not niches:
                st.error("Pick at least 1 city and 1 niche")
            else:
                with st.spinner("Finding leads…"):
                    try:
                        result = run_bulk_pipeline(
                            region=region,
                            cities=cities,
                            niches=niches,
                            limit_per=per,
                            analyze_ads=True,
                            drop_chains=True,
                            sync_sheets=True,
                        )
                        st.success(result["summary"])
                        st.session_state["nav"] = "Leads"
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    with tab_one:
        region = st.selectbox(
            "Region",
            list(REGIONS.keys()),
            format_func=lambda x: REGIONS[x]["label"],
            key="one_region",
        )
        city = st.selectbox("City", suggest_cities(region) + ["Other…"], key="one_city")
        if city == "Other…":
            city = st.text_input("City name", value="Akbarpur")
        niche_opts = suggest_niches()
        niche = st.selectbox(
            "Niche",
            [n["id"] for n in niche_opts],
            format_func=lambda i: next(n["label"] for n in niche_opts if n["id"] == i),
        )
        limit = st.slider("Max leads", 10, 50, 25)
        if st.button("Run one city", type="primary", use_container_width=True):
            with st.spinner("Working…"):
                try:
                    result = run_full_pipeline(
                        region=region,
                        city=city,
                        niche=niche,
                        limit=limit,
                        auto_experience=False,
                        analyze_ads=True,
                        drop_chains=True,
                        sync_sheets=True,
                    )
                    st.success(result["summary"])
                except Exception as e:
                    st.error(str(e))

    with tab_real:
        st.markdown(
            """
### Make it REAL (exact steps)

Demo mode only creates practice shops. For real independent shops:

#### 1) Free Gemini key
1. Open https://aistudio.google.com/apikey  
2. Create API key → copy it  

#### 2) Streamlit Secrets
App → ⋮ → **Settings → Secrets** → paste:

```toml
SCRAPER_MODE = "light"
GEMINI_API_KEY = "YOUR_KEY_HERE"
LLM_MODEL = "google_genai/gemini-2.0-flash"
DASHBOARD_PASSWORD = "your-password"
AGENCY_NAME = "Your Web Agency"
AGENCY_WHATSAPP = "+91XXXXXXXXXX"
```

#### 3) Save → Reboot app → login

#### 4) Run **Bulk find** again
Use 3–5 cities × 4 niches.  
`light` mode = free Gemini reads public search pages (no Playwright).

#### 5) Optional: Google Sheets (keep leads forever)
See **Sheets** page.

#### Modes
| Mode | What it does | Free host OK? |
|------|----------------|---------------|
| `demo` | Sample leads, lots of volume | ✅ |
| `light` | Real public-page + Gemini extract (local markets + social shops) | ✅ best on Streamlit |
| `open_source` | Full ScrapeGraphAI + browser | ❌ needs VPS/PC |

#### What “local niche hunt” targets
- Dedicated niches: café, jeweller, clothing, shoes, multi-retail  
- Local markets / roads inside the town (not only city center)  
- Shops with Instagram/Facebook  
- Paid product ads **or** organic product posts  
- Social-first shops that need a website / product showcase  
"""
        )
        if h.get("scraper_mode") == "demo":
            st.error("Still on demo — change Secrets to `light` + Gemini for real shops.")
        elif h.get("ready"):
            st.success("Ready for real/light scraping.")


def page_sheets():
    st.markdown("### ☁️ Sheets")
    sh = sheets_status()
    st.write("Connected:" , "✅" if sh["enabled"] else "❌")
    st.markdown(
        """
1. Create Google Sheet → copy Sheet ID  
2. Cloud Console → enable Sheets + Drive API  
3. Service account JSON key  
4. Share sheet with service account email (Editor)  
5. Secrets:

```toml
GOOGLE_SHEET_ID = "..."
GOOGLE_SHEET_WORKSHEET = "Leads"
SHEETS_AUTO_SYNC = "true"
GOOGLE_SERVICE_ACCOUNT_JSON = \"\"\"{...}\"\"\"
```
"""
    )
    if st.button("Push all leads to Sheets", type="primary", use_container_width=True):
        try:
            st.success(push_leads_to_sheets(load_leads()))
        except Exception as e:
            st.error(str(e))
    if st.button("Download Excel", use_container_width=True):
        path = export_leads_excel()
        with open(path, "rb") as f:
            st.download_button("Save leads.xlsx", f, "leads.xlsx", use_container_width=True)


def page_guide():
    st.markdown("### 🧮 Score guide")
    st.write(
        "Highest score = independent shop + **product ads** (IG/FB/Google) + weak/no website."
    )
    st.dataframe(pd.DataFrame(SCORE_FACTOR_GUIDE), use_container_width=True, hide_index=True)
    st.markdown("#### Recent activity")
    acts = recent_activity(12)
    if acts:
        st.dataframe(pd.DataFrame(acts), use_container_width=True, hide_index=True)


def page_settings():
    st.markdown("### ⚙️ Settings")
    s = get_settings()
    h = health_check()
    st.json(
        {
            "scraper_mode": s["scraper_mode"],
            "llm_model": s["llm_model"],
            "llm_key_present": bool(s["llm_api_key"]),
            "ready": h["ready"],
            "agency_name": s["agency_name"],
            "sheets": sheets_status(),
        }
    )
    if st.button("Log out", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()


def main():
    inject_css()
    if not check_password():
        return

    if "nav" not in st.session_state:
        st.session_state["nav"] = "Home"

    # top compact nav — large touch targets, single row wrap
    st.markdown("## 🏪 Lead Agent")
    nav_items = ["Home", "Leads", "Find leads", "Sheets", "Guide", "Settings"]
    st.session_state["nav"] = st.radio(
        "Menu",
        nav_items,
        index=nav_items.index(st.session_state["nav"])
        if st.session_state["nav"] in nav_items
        else 0,
        horizontal=True,
        label_visibility="collapsed",
    )

    page = st.session_state["nav"]
    if page == "Home":
        page_home()
    elif page == "Leads":
        page_leads()
    elif page == "Find leads":
        page_find()
    elif page == "Sheets":
        page_sheets()
    elif page == "Guide":
        page_guide()
    else:
        page_settings()


if __name__ == "__main__":
    main()
