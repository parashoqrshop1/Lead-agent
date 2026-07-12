"""
Independent Shop Lead Agent — Streamlit Cloud safe entrypoint.
Keep top-level imports minimal to avoid native segfaults.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st


def _safe_import_error(title: str, err: Exception) -> None:
    st.error(f"{title}: {err}")
    st.info(
        "If this is a Cloud crash loop, set Python **3.12** in Streamlit app settings "
        "(Advanced settings), then Reboot. Streamlit ignores runtime.txt."
    )


def _read_password() -> str:
    try:
        val = st.secrets.get("DASHBOARD_PASSWORD", None)
        if val is not None and str(val).strip():
            return str(val).strip()
    except Exception:
        pass
    import os

    return (os.getenv("DASHBOARD_PASSWORD") or "change-me-now").strip() or "change-me-now"


def login() -> bool:
    if st.session_state.get("authenticated"):
        return True
    expected = _read_password()
    st.markdown("## 🔐 Lead Agent")
    st.caption("Independent shops · local niches · free stack")
    with st.form("login"):
        pwd = st.text_input("Password", type="password")
        ok = st.form_submit_button("Enter", type="primary", use_container_width=True)
    if ok:
        if (pwd or "").strip() == expected:
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("Wrong password")
    if expected == "change-me-now":
        st.caption("Default password: `change-me-now`")
        if st.button("Open with default password", use_container_width=True):
            st.session_state["authenticated"] = True
            st.rerun()
    return False


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 0.8rem; max-width: 720px; }
        .lead-card {
            border: 1px solid #334155; border-radius: 16px; padding: 14px;
            margin: 0 0 12px 0; background: #0f172a;
        }
        .lead-name { font-weight: 700; color: #f8fafc; }
        .lead-meta { color: #94a3b8; font-size: 0.9rem; }
        .pill {
            display:inline-block; padding:3px 10px; border-radius:999px;
            font-size:0.78rem; font-weight:700; margin-right:6px;
        }
        .pill-hi { background:#14532d; color:#86efac; }
        .pill-mid { background:#713f12; color:#fde68a; }
        .pill-lo { background:#7f1d1d; color:#fecaca; }
        .pill-ad { background:#1e3a8a; color:#bfdbfe; }
        button { min-height: 2.6rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def score_pill(score: int) -> str:
    cls = "pill-hi" if score >= 70 else "pill-mid" if score >= 45 else "pill-lo"
    return f'<span class="pill {cls}">{score}/100</span>'


def card_html(lead) -> str:
    ads = ""
    if getattr(lead, "runs_ads", None) or (getattr(lead, "ad_style", None) or "").startswith("product"):
        ads = f'<span class="pill pill-ad">📣 {lead.ad_style or "social"}</span>'
    return f"""
    <div class="lead-card">
      <div class="lead-name">{lead.business_name}</div>
      <div class="lead-meta">{lead.niche or 'shop'} · {lead.city or '—'} · {lead.phone or lead.whatsapp or 'no phone'}</div>
      {score_pill(int(lead.lead_score or 0))}
      {ads}
      <div class="lead-meta">IG: {lead.instagram or '—'} · FB: {lead.facebook or '—'}</div>
    </div>
    """


def page_home(storage, scraper):
    st.markdown("### 🏠 Home")
    try:
        leads = [l for l in storage.load_leads() if not l.is_branded_chain]
    except Exception as e:
        _safe_import_error("Could not load leads", e)
        return

    h = scraper.health_check()
    c1, c2, c3 = st.columns(3)
    c1.metric("Leads", len(leads))
    c2.metric("Score ≥70", sum(1 for l in leads if (l.lead_score or 0) >= 70))
    c3.metric("With social", sum(1 for l in leads if l.instagram or l.facebook))

    st.info(
        f"Mode: **{h.get('scraper_mode')}** · Ready: **{h.get('ready')}** · "
        f"Gemini key: **{'yes' if h.get('llm_key_present') else 'no'}**"
    )
    if h.get("scraper_mode") == "demo":
        st.warning(
            "Demo mode (sample leads). For real shops later: Secrets "
            '`SCRAPER_MODE="light"` + GEMINI_API_KEY (needs stable Cloud Python).'
        )

    if st.button("📍 Hunt local niche leads", type="primary", use_container_width=True):
        st.session_state["nav"] = "Find leads"
        st.rerun()
    if st.button("📋 Open inbox", use_container_width=True):
        st.session_state["nav"] = "Leads"
        st.rerun()

    top = sorted(leads, key=lambda x: x.lead_score or 0, reverse=True)[:5]
    st.markdown("#### Top leads")
    if not top:
        st.caption("No leads yet — open Find leads.")
    for lead in top:
        st.markdown(card_html(lead), unsafe_allow_html=True)


def page_leads(storage, experience, ads, scoring):
    st.markdown("### 📋 Leads")
    leads = [l for l in storage.load_leads() if not l.is_branded_chain]
    if not leads:
        st.warning("No leads yet. Use Find leads.")
        return

    q = st.text_input("Search name / city / phone")
    min_score = st.select_slider("Min score", options=[0, 40, 60, 70, 80, 90], value=0)
    only_social = st.toggle("Only with Instagram/Facebook", value=False)
    only_product = st.toggle("Product ads / product posts", value=False)

    filtered = []
    for l in leads:
        if (l.lead_score or 0) < min_score:
            continue
        if only_social and not (l.instagram or l.facebook):
            continue
        if only_product and (l.ad_style or "").lower() not in (
            "product_showcase",
            "product",
            "mixed",
            "catalogue",
        ) and not l.runs_ads:
            continue
        blob = f"{l.business_name} {l.city} {l.phone} {l.niche} {l.ad_topics}".lower()
        if q and q.lower() not in blob:
            continue
        filtered.append(l)
    filtered.sort(key=lambda x: x.lead_score or 0, reverse=True)
    st.caption(f"{len(filtered)} leads")

    if not filtered:
        st.info("No matches.")
        return

    labels = {
        f"{l.lead_score} · {l.business_name} · {l.city or ''}": l.id for l in filtered
    }
    keys = list(labels.keys())
    choice = st.selectbox("Pick a lead", keys)
    lead = next(l for l in filtered if l.id == labels[choice])

    st.markdown(card_html(lead), unsafe_allow_html=True)
    st.write(f"**Phone:** {lead.phone or lead.whatsapp or '—'}")
    st.write(f"**Email:** {lead.email or '—'}")
    st.write(f"**Instagram:** {lead.instagram or '—'}")
    st.write(f"**Facebook:** {lead.facebook or '—'}")
    st.write(f"**Website:** {lead.website or 'none'}")
    st.write(f"**Ads:** {lead.ad_platforms or '—'} · {lead.ad_style or '—'} · {lead.ad_topics or '—'}")
    st.write(f"**Pain:** {lead.pain_points or '—'}")

    with st.expander("Why this score?"):
        factors = scoring.factors_table_for_lead(lead)
        if factors:
            import pandas as pd

            st.dataframe(pd.DataFrame(factors), use_container_width=True, hide_index=True)
        st.caption(lead.score_breakdown or "")

    from config.settings import LEAD_STATUSES

    status = st.selectbox(
        "Status",
        LEAD_STATUSES,
        index=LEAD_STATUSES.index(lead.status) if lead.status in LEAD_STATUSES else 0,
    )
    notes = st.text_area("Notes", value=lead.notes or "", height=80)
    if st.button("💾 Save", type="primary", use_container_width=True):
        storage.update_lead(lead.id, status=status, notes=notes)
        st.success("Saved")
        st.rerun()

    if st.button("✨ WhatsApp pitch", use_container_width=True):
        prop = experience.build_experience_proposal(lead, use_llm=False)
        st.session_state["wa"] = prop.outreach_whatsapp
        st.success(prop.package_name)

    st.text_area(
        "Copy WhatsApp",
        value=st.session_state.get("wa") or experience.draft_quick_outreach(lead),
        height=180,
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("📣 Re-check ads", use_container_width=True):
            storage.upsert_leads([ads.analyze_ads_heuristic(lead)])
            st.rerun()
    with c2:
        if st.button("🗑 Delete", use_container_width=True):
            storage.delete_lead(lead.id)
            st.rerun()

    if st.button("🧹 Remove duplicate leads", use_container_width=True):
        result = storage.purge_duplicate_leads()
        st.success(f"Cleaned {result['before']} → {result['after']} (removed {result['removed']})")
        st.rerun()

    import pandas as pd

    st.download_button(
        "⬇️ CSV",
        data=storage.leads_dataframe().to_csv(index=False).encode("utf-8"),
        file_name="leads.csv",
        mime="text/csv",
        use_container_width=True,
    )


def page_find(orchestrator, scraper, storage):
    st.markdown("### ⚡ Find leads")
    h = scraper.health_check()
    mode = h.get("scraper_mode")
    has_key = h.get("llm_key_present")
    st.caption(f"Mode: `{mode}` · Gemini key: {'✅' if has_key else '❌'}")

    # Loud mode banner so user knows demo vs real
    if mode == "demo":
        st.error(
            "⚠️ Currently DEMO mode — sample practice leads only.\n\n"
            "For REAL shops set Secrets:\n"
            '`SCRAPER_MODE = "light"` + `GEMINI_API_KEY = "your_key"` then Reboot.'
        )
    elif mode in ("light", "gemini_web") and has_key:
        st.success("✅ REAL mode ready (light + Gemini key). Local hunt uses live public search.")
    else:
        st.warning("Mode is not fully ready for real scrape. Check Secrets.")

    from config.niches import REGIONS

    # Always-visible emergency generator (never empty)
    if st.button("⚡ Generate leads NOW (guaranteed)", type="primary", use_container_width=True):
        with st.spinner("Generating leads…"):
            try:
                result = orchestrator.run_hyperlocal_pipeline(
                    region="india",
                    city="Akbarpur",
                    niches=["cafe", "jeweller", "clothing", "shoes", "multi_retail"],
                    limit=60,
                    deep_local=True,
                    max_localities=8,
                    analyze_ads=True,
                    drop_chains=True,
                    sync_sheets=False,
                )
                st.session_state["last_hunt"] = result
                n = len(storage.load_leads())
                st.success(f"{result.get('summary')} · Stored total now: {n}")
                if result.get("errors"):
                    for e in result["errors"][:6]:
                        st.warning(str(e))
                # show table immediately
                leads = storage.load_leads()
                if leads:
                    import pandas as pd

                    rows = [
                        {
                            "score": l.lead_score,
                            "name": l.business_name,
                            "city": l.city,
                            "phone": l.phone or l.whatsapp,
                            "instagram": l.instagram,
                            "niche": l.niche,
                        }
                        for l in sorted(leads, key=lambda x: x.lead_score or 0, reverse=True)[:40]
                    ]
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                else:
                    st.error("Still 0 stored leads after run — report this.")
            except Exception as e:
                st.exception(e)

    tab_local, tab_bulk, tab_real = st.tabs(["📍 Local niches", "🔥 Multi-city", "🚀 Go real"])

    with tab_local:
        st.write(
            "Hunt dedicated niches in local markets. Prefers shops with Instagram/Facebook "
            "(ads or organic product posts)."
        )
        region = st.selectbox(
            "Region",
            list(REGIONS.keys()),
            format_func=lambda x: REGIONS[x]["label"],
            key="r1",
        )
        cities = scraper.suggest_cities(region)
        default = "Akbarpur" if "Akbarpur" in cities else cities[0]
        city = st.selectbox(
            "City / town",
            cities + ["Other…"],
            index=(cities + ["Other…"]).index(default) if default in cities else 0,
            key="c1",
        )
        if city == "Other…":
            city = st.text_input("Town name", value="Akbarpur", key="c1x")
        niche_opts = scraper.suggest_niches()
        niche_ids = [n["id"] for n in niche_opts if n["id"] != "other_independent"]
        niches = st.multiselect(
            "Niches",
            niche_ids,
            default=["cafe", "jeweller", "clothing", "shoes", "multi_retail"],
            format_func=lambda i: next(n["label"] for n in niche_opts if n["id"] == i),
            key="n1",
        )
        limit = st.slider("Target unique leads", 20, 120, 50, key="l1")
        deep = st.toggle("Scan local markets / roads", value=True)
        areas = st.slider("Max localities", 3, 12, 8, key="a1")
        if st.button("📍 Hunt local niche leads", type="primary", use_container_width=True):
            if not city or not niches:
                st.error("Pick city + niches")
            else:
                with st.spinner(f"Hunting around {city}…"):
                    try:
                        result = orchestrator.run_hyperlocal_pipeline(
                            region=region,
                            city=city,
                            niches=niches,
                            limit=limit,
                            deep_local=deep,
                            max_localities=areas,
                            analyze_ads=True,
                            drop_chains=True,
                            sync_sheets=False,
                        )
                        st.session_state["last_hunt"] = result
                        n = len(storage.load_leads())
                        st.success(f"{result.get('summary')} · Total stored: {n}")
                        if result.get("errors"):
                            for e in result["errors"][:8]:
                                st.warning(str(e))
                        leads = [l for l in storage.load_leads() if not l.is_branded_chain]
                        if leads:
                            import pandas as pd

                            rows = [
                                {
                                    "score": l.lead_score,
                                    "name": l.business_name,
                                    "city": l.city,
                                    "phone": l.phone or l.whatsapp,
                                    "ig": (l.instagram or "")[:40],
                                    "niche": l.niche,
                                    "ads": l.ad_style,
                                }
                                for l in sorted(leads, key=lambda x: x.lead_score or 0, reverse=True)[:50]
                            ]
                            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                            st.info("Open top menu → **Leads** to pitch WhatsApp.")
                        else:
                            st.error("0 leads stored. Tap 'Generate leads NOW' above.")
                    except Exception as e:
                        st.exception(e)

    with tab_bulk:
        region = st.selectbox(
            "Region",
            list(REGIONS.keys()),
            format_func=lambda x: REGIONS[x]["label"],
            key="r2",
        )
        city_opts = scraper.suggest_cities(region)
        cities = st.multiselect(
            "Cities",
            city_opts,
            default=[c for c in ["Akbarpur", "Lucknow", "Kanpur", "Ayodhya"] if c in city_opts][:3]
            or city_opts[:3],
            key="c2",
        )
        niche_opts = scraper.suggest_niches()
        niches = st.multiselect(
            "Niches",
            [n["id"] for n in niche_opts if n["id"] != "other_independent"],
            default=["cafe", "jeweller", "clothing", "shoes"],
            format_func=lambda i: next(n["label"] for n in niche_opts if n["id"] == i),
            key="n2",
        )
        per = st.slider("Leads per city×niche", 10, 40, 20, key="p2")
        if st.button("🚀 Run multi-city bulk", type="primary", use_container_width=True):
            with st.spinner("Bulk finding…"):
                try:
                    result = orchestrator.run_bulk_pipeline(
                        region=region,
                        cities=cities,
                        niches=niches,
                        limit_per=per,
                        analyze_ads=True,
                        drop_chains=True,
                        sync_sheets=False,
                    )
                    st.success(result["summary"])
                    st.session_state["nav"] = "Leads"
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with tab_real:
        st.markdown(
            """
### Make leads REAL (exact)

1. Get free Gemini key: https://aistudio.google.com/apikey  
2. Streamlit app → **⋮ → Settings → Secrets** → paste:

```toml
SCRAPER_MODE = "light"
GEMINI_API_KEY = "PASTE_YOUR_KEY"
LLM_MODEL = "gemini-2.0-flash"
DASHBOARD_PASSWORD = "your-password"
AGENCY_NAME = "Your Web Agency"
AGENCY_WHATSAPP = "+91XXXXXXXXXX"
```

3. **Save** → **Manage app → Reboot**
4. Login → **Find leads → Local niches**
5. City: your town (e.g. Akbarpur) · niches: café/jeweller/clothing/shoes
6. Run **Hunt local niche leads**

This uses **real public web search + free Gemini REST API** (no fake demo data).

### What you get (when public)
Phone / WhatsApp, Instagram, Facebook, website, address, ads style/topics, score.

### Tip
If Cloud is unstable, still set Python **3.12** in Advanced settings when available.
"""
        )
        # live readiness for real mode
        if h.get("scraper_mode") in ("light", "gemini_web", "open_source") and h.get("llm_key_present"):
            st.success("Real mode secrets look ready. Run Local niches now.")
        elif h.get("llm_key_present"):
            st.warning('Gemini key found. Set SCRAPER_MODE = "light" then Reboot.')
        else:
            st.error("No GEMINI_API_KEY in Secrets yet — still demo/fake leads.")


def page_guide(scoring, storage):
    st.markdown("### 🧮 Score guide")
    st.write(
        "High score = independent niche shop + social product posts/ads + weak/no website."
    )
    import pandas as pd

    st.dataframe(pd.DataFrame(scoring.SCORE_FACTOR_GUIDE), use_container_width=True, hide_index=True)
    acts = storage.recent_activity(10)
    if acts:
        st.dataframe(pd.DataFrame(acts), use_container_width=True, hide_index=True)


def page_settings(scraper):
    st.markdown("### ⚙️ Settings")
    from config.settings import get_settings

    s = get_settings()
    h = scraper.health_check()
    st.json(
        {
            "scraper_mode": s.get("scraper_mode"),
            "llm_key_present": bool(s.get("llm_api_key")),
            "ready": h.get("ready"),
            "agency_name": s.get("agency_name"),
            "python_note": "If Cloud uses 3.14 and crashes, set Python 3.12 in Streamlit UI settings",
        }
    )
    if st.button("Log out", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()


def main():
    inject_css()
    if not login():
        return

    # Lazy import agent modules only after login (reduces crash risk at boot)
    try:
        from agents import ads_agent as ads
        from agents import experience_agent as experience
        from agents import orchestrator
        from agents import scraper_agent as scraper
        from agents import scoring
        from agents import storage
    except Exception as e:
        _safe_import_error("Failed loading agent modules", e)
        return

    if "nav" not in st.session_state:
        st.session_state["nav"] = "Home"

    st.markdown("## 🏪 Lead Agent")
    nav = ["Home", "Leads", "Find leads", "Guide", "Settings"]
    st.session_state["nav"] = st.radio(
        "Menu",
        nav,
        index=nav.index(st.session_state["nav"]) if st.session_state["nav"] in nav else 0,
        horizontal=True,
        label_visibility="collapsed",
    )

    page = st.session_state["nav"]
    try:
        if page == "Home":
            page_home(storage, scraper, orchestrator)
        elif page == "Leads":
            page_leads(storage, experience, ads, scoring)
        elif page == "Find leads":
            page_find(orchestrator, scraper, storage)
        elif page == "Guide":
            page_guide(scoring, storage)
        else:
            page_settings(scraper)
    except Exception as e:
        _safe_import_error("Page error", e)


if __name__ == "__main__":
    # imported by boot entrypoint
    main()
