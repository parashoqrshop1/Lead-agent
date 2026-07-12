"""
Independent Shop Lead Agent — Advanced Dashboard
FREE: Gemini + ScrapeGraphAI + Google Sheets + transparent scoring + ads intel

Run: streamlit run dashboard/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st

from agents.ads_agent import analyze_ads_heuristic, analyze_ads_with_llm, enrich_ads_batch
from agents.experience_agent import build_experience_proposal, draft_quick_outreach
from agents.lead_schema import AgentTask, ShopLead
from agents.orchestrator import run_full_pipeline
from agents.scraper_agent import (
    enrich_lead_from_url,
    extract_leads_from_url,
    health_check,
    search_leads,
    suggest_cities,
    suggest_niches,
)
from agents.scoring import SCORE_FACTOR_GUIDE, factors_table_for_lead
from agents.sheets_store import (
    pull_leads_from_sheets,
    push_leads_to_sheets,
    sheets_status,
    sync_local_and_sheets,
)
from agents.storage import (
    add_task,
    delete_lead,
    export_leads_excel,
    leads_dataframe,
    load_leads,
    load_proposals,
    load_tasks,
    recent_activity,
    save_leads,
    update_lead,
    update_task,
)
from config.niches import REGIONS, niche_label
from config.settings import LEAD_STATUSES, get_settings

st.set_page_config(
    page_title="Independent Shop Lead Agent",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _read_dashboard_password() -> str:
    """Read password fresh every time (do not use cached settings for auth)."""
    # 1) Streamlit secrets
    try:
        if hasattr(st, "secrets"):
            # st.secrets.get works on Cloud; avoid fragile `key in st.secrets`
            val = st.secrets.get("DASHBOARD_PASSWORD", None)
            if val is not None and str(val).strip() != "":
                return str(val).strip()
    except Exception:
        pass
    # 2) env
    import os

    env = (os.getenv("DASHBOARD_PASSWORD") or "").strip()
    if env:
        return env
    # 3) default
    return "change-me-now"


def check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True

    expected = _read_dashboard_password()

    st.title("🔐 Lead Agent Login")
    st.caption("Independent shops · Ads-aware scoring · Google Sheets CRM")

    # st.form is more reliable on mobile (keyboard "Go" submits)
    with st.form("login_form", clear_on_submit=False):
        pwd = st.text_input(
            "Dashboard password",
            type="password",
            placeholder="Type password from Streamlit Secrets",
        )
        submitted = st.form_submit_button(
            "Enter dashboard",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        typed = (pwd or "").strip()
        if typed == expected:
            st.session_state["authenticated"] = True
            st.success("Login OK — loading…")
            st.rerun()
        else:
            st.error(
                "Wrong password.\n\n"
                "Fix: Streamlit app → ⋮ → Settings → Secrets → set\n"
                '`DASHBOARD_PASSWORD = "your-password"`\n'
                "then Save and try again.\n\n"
                f"(Expected password length: {len(expected)} characters. "
                f"You typed: {len(typed)} characters.)"
            )
            if expected == "change-me-now":
                st.warning(
                    "No DASHBOARD_PASSWORD found in Secrets. "
                    "Default is exactly: change-me-now"
                )

    # One-tap demo unlock if still on default (helps phone testing)
    if expected == "change-me-now":
        st.caption("Default password is: `change-me-now`")
        if st.button("🚀 Open with default password", use_container_width=True):
            st.session_state["authenticated"] = True
            st.rerun()

    st.info(
        "Tip: password must match Secrets exactly (no extra spaces). "
        "After changing Secrets, wait 10s or Reboot the app."
    )
    return False


def inject_css():
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.1rem; max-width: 1200px; }
        div[data-testid="stMetric"] {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            border: 1px solid #334155; border-radius: 12px; padding: 12px 14px;
        }
        div[data-testid="stMetric"] label { color: #94a3b8 !important; }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #f8fafc !important; }
        .score-hi { color: #4ade80; font-weight: 700; }
        .score-mid { color: #fbbf24; font-weight: 700; }
        .score-lo { color: #f87171; font-weight: 700; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def score_class(score: int) -> str:
    if score >= 70:
        return "score-hi"
    if score >= 45:
        return "score-mid"
    return "score-lo"


def page_overview():
    st.subheader("📊 Overview")
    df = leads_dataframe()
    health = health_check()
    sh = sheets_status()
    total = len(df) if not df.empty else 0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    indep = int((df["is_independent"] == True).sum()) if total and "is_independent" in df else 0  # noqa: E712
    ads = int((df["runs_ads"] == True).sum()) if total and "runs_ads" in df else 0  # noqa: E712
    product_ads = 0
    if total and "ad_style" in df:
        product_ads = int(
            df["ad_style"].fillna("").str.lower().isin(
                ["product_showcase", "product", "mixed", "catalogue"]
            ).sum()
        )
    no_web = int((df["has_website"] == False).sum()) if total and "has_website" in df else 0  # noqa: E712
    avg_score = int(df["lead_score"].mean()) if total else 0

    c1.metric("Total leads", total)
    c2.metric("Independent", indep)
    c3.metric("Run ads", ads)
    c4.metric("Product ads", product_ads)
    c5.metric("No website", no_web)
    c6.metric("Avg score", avg_score)

    st.divider()
    left, right = st.columns([1.2, 1])
    with left:
        st.markdown("#### Score distribution")
        if total:
            fig = px.histogram(df, x="lead_score", nbins=12, color_discrete_sequence=["#14b8a6"])
            fig.update_layout(
                height=280, margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#e2e8f0",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No leads yet — run **Agents → Full Pipeline** (demo works with zero keys).")

        st.markdown("#### By niche")
        if total and "niche" in df:
            niche_counts = df["niche"].fillna("unknown").value_counts().reset_index()
            niche_counts.columns = ["niche", "count"]
            fig2 = px.bar(niche_counts, x="niche", y="count", color="count", color_continuous_scale="Teal")
            fig2.update_layout(
                height=280, margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#e2e8f0",
            )
            st.plotly_chart(fig2, use_container_width=True)

    with right:
        st.markdown("#### System (FREE)")
        st.write(f"**Scraper:** {'✅ Ready' if health['ready'] else '⚠️ demo or add Gemini key'}")
        st.write(f"**Mode:** `{health['scraper_mode']}` · **LLM:** `{health['llm_model']}`")
        st.write(f"**Gemini key:** {'✅' if health['llm_key_present'] else '❌'}")
        st.write(
            f"**Google Sheets:** {'✅ connected' if sh['enabled'] else '❌ not configured'}"
            + (f" · sheet `{sh['worksheet']}`" if sh["enabled"] else "")
        )
        st.write(f"**Agency:** {health['agency_name']}")
        st.caption(health.get("stack_note", ""))

        st.markdown("#### Why high scores?")
        st.write("🔥 **Product ads** (IG/FB/Google showing products) = top leads")
        st.write("📈 Ads + weak website = conversion-gap gold")
        st.write("🏪 Independent multi-brand / high variety")
        st.write("📄 Full factor table → **Score guide** page")

        st.markdown("#### Recent activity")
        acts = recent_activity(10)
        if acts:
            st.dataframe(pd.DataFrame(acts), use_container_width=True, hide_index=True)
        else:
            st.caption("No activity yet.")


def page_leads():
    st.subheader("📋 Leads inbox")
    df = leads_dataframe()
    f1, f2, f3, f4, f5, f6 = st.columns(6)
    with f1:
        status_f = st.multiselect("Status", LEAD_STATUSES, default=[])
    with f2:
        niche_f = st.multiselect("Niche", [n["id"] for n in suggest_niches()])
    with f3:
        city_f = st.text_input("City contains")
    with f4:
        min_score = st.slider("Min score", 0, 100, 0)
    with f5:
        only_indep = st.checkbox("Independent only", value=True)
    with f6:
        only_ads = st.checkbox("Runs ads only", value=False)
        only_product = st.checkbox("Product ads only", value=False)

    if df.empty:
        st.warning("No leads yet. Run Agents → Full Pipeline.")
        return

    view = df.copy()
    if status_f:
        view = view[view["status"].isin(status_f)]
    if niche_f:
        view = view[view["niche"].isin(niche_f)]
    if city_f:
        view = view[view["city"].fillna("").str.contains(city_f, case=False)]
    if min_score:
        view = view[view["lead_score"] >= min_score]
    if only_indep and "is_branded_chain" in view.columns:
        view = view[view["is_branded_chain"] != True]  # noqa: E712
    if only_ads and "runs_ads" in view.columns:
        view = view[view["runs_ads"] == True]  # noqa: E712
    if only_product and "ad_style" in view.columns:
        view = view[
            view["ad_style"].fillna("").str.lower().isin(
                ["product_showcase", "product", "mixed", "catalogue"]
            )
        ]

    view = view.sort_values("lead_score", ascending=False)
    st.caption(f"Showing {len(view)} / {len(df)} leads — sorted by score")

    show_cols = [
        c
        for c in [
            "id",
            "business_name",
            "niche",
            "city",
            "phone",
            "has_website",
            "runs_ads",
            "ad_style",
            "ad_platforms",
            "ad_topics",
            "lead_score",
            "score_breakdown",
            "status",
        ]
        if c in view.columns
    ]
    st.dataframe(view[show_cols], use_container_width=True, hide_index=True, height=340)

    st.markdown("#### Act on a lead")
    ids = view["id"].tolist()
    if not ids:
        return
    selected = st.selectbox("Lead id", [str(x) for x in ids])
    # Prefer loading from JSON storage (clean types) over pandas row
    lead = None
    for item in load_leads():
        if str(item.id) == str(selected):
            lead = item
            break
    if lead is None:
        row = view[view["id"].astype(str) == str(selected)].iloc[0]
        lead = ShopLead.from_any(row)

    a, b = st.columns(2)
    with a:
        st.markdown(f"### {lead.business_name}")
        st.markdown(
            f'Score <span class="{score_class(lead.lead_score)}">{lead.lead_score}/100</span> · '
            f'{niche_label(lead.niche or "")}',
            unsafe_allow_html=True,
        )
        st.write(f"📍 {lead.city or '—'}, {lead.country or '—'}")
        st.write(f"📞 {lead.phone or lead.whatsapp or '—'} · ✉️ {lead.email or '—'}")
        st.write(f"🌐 {lead.website or 'no website'} ({lead.website_quality or 'n/a'})")
        st.write(f"IG: {lead.instagram or '—'} · FB: {lead.facebook or '—'}")
        st.write(f"Variety: {lead.product_variety or '—'} · Multi-brand: {lead.carries_multiple_brands}")

        st.markdown("##### 📣 Ads intelligence")
        st.write(f"**Runs ads:** {lead.runs_ads} · **Style:** `{lead.ad_style or '—'}`")
        st.write(f"**Platforms:** {lead.ad_platforms or '—'}")
        st.write(f"**Topics:** {lead.ad_topics or '—'}")
        st.write(f"**Evidence:** {lead.ads_evidence or '—'}")
        st.write(
            f"IG ads: {lead.has_instagram_ads} · FB ads: {lead.has_facebook_ads} · Google ads: {lead.has_google_ads}"
        )

        st.markdown("##### 🧮 Score factors (this lead)")
        factors = factors_table_for_lead(lead)
        if factors:
            st.dataframe(pd.DataFrame(factors), use_container_width=True, hide_index=True)
        st.caption(lead.score_breakdown or "")

        new_status = st.selectbox(
            "Status",
            LEAD_STATUSES,
            index=LEAD_STATUSES.index(lead.status) if lead.status in LEAD_STATUSES else 0,
        )
        notes = st.text_area("Notes", value=lead.notes or "")
        if st.button("💾 Save", type="primary"):
            update_lead(lead.id, status=new_status, notes=notes)
            st.success("Saved (+ Sheets if auto-sync on)")
            st.rerun()
        if st.button("🗑 Delete"):
            delete_lead(lead.id)
            st.rerun()

    with b:
        st.markdown("#### Ads re-check + experience")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📣 Ads heuristic", use_container_width=True):
                lead2 = analyze_ads_heuristic(lead)
                from agents.storage import upsert_leads

                upsert_leads([lead2])
                st.success(f"Score now {lead2.lead_score}")
                st.rerun()
        with c2:
            if st.button("🤖 Ads via Gemini", use_container_width=True):
                with st.spinner("Analyzing ads…"):
                    lead2 = analyze_ads_with_llm(lead)
                    from agents.storage import upsert_leads

                    upsert_leads([lead2])
                    st.success(f"Score now {lead2.lead_score}")
                    st.rerun()

        if st.button("✨ Experience proposal", type="primary", use_container_width=True):
            with st.spinner("Building package + outreach…"):
                prop = build_experience_proposal(lead, use_llm=False)
                st.session_state["last_proposal"] = prop.model_dump()
                st.success(f"Package: {prop.package_name}")
                st.rerun()

        prop_data = st.session_state.get("last_proposal")
        if prop_data and prop_data.get("lead_id") == lead.id:
            st.write(f"**{prop_data.get('headline')}**")
            st.write(prop_data.get("summary"))
            for p in prop_data.get("pillars") or []:
                st.write(f"• {p}")
            st.text_area("WhatsApp", value=prop_data.get("outreach_whatsapp", ""), height=160)
            st.text_area("Email", value=prop_data.get("outreach_email", ""), height=160)
        else:
            st.text_area("Quick WhatsApp", value=draft_quick_outreach(lead), height=180)

        if lead.website:
            if st.button("🔎 Enrich from website"):
                with st.spinner("Enriching…"):
                    try:
                        enrich_lead_from_url(lead.website, lead)
                        st.success("Enriched")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        csv = view.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ CSV", csv, "leads.csv", "text/csv")
    with c2:
        if st.button("⬇️ Build Excel"):
            path = export_leads_excel()
            with open(path, "rb") as f:
                st.download_button(
                    "Save Excel",
                    f,
                    "leads.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
    with c3:
        if st.button("☁️ Push all to Google Sheets"):
            try:
                res = push_leads_to_sheets(load_leads())
                st.success(res)
            except Exception as e:
                st.error(str(e))


def page_agents():
    st.subheader("🤖 Multi-agent control")
    health = health_check()
    if not health["ready"]:
        st.warning(
            "Live scrape needs free Gemini key + open_source mode, or set SCRAPER_MODE=demo."
        )

    tab1, tab2, tab3, tab4 = st.tabs(
        ["🚀 Full Pipeline", "🔍 Discover", "🌐 URL", "📝 Task"]
    )

    with tab1:
        st.markdown(
            """
**Pipeline:** Discover → Qualify → **Ads intel** → Score factors → Experience → **Google Sheets**

Highest scores go to independent shops that **advertise products** on Instagram / Facebook / Google
but still need a strong website/experience.
"""
        )
        r1, r2 = st.columns(2)
        with r1:
            region = st.selectbox(
                "Region",
                list(REGIONS.keys()),
                format_func=lambda x: REGIONS[x]["label"],
            )
            cities = suggest_cities(region)
            city = st.selectbox("City", options=cities + ["Other…"])
            if city == "Other…":
                city = st.text_input("City name", value="Akbarpur")
        with r2:
            niches = suggest_niches()
            niche = st.selectbox(
                "Niche",
                options=[n["id"] for n in niches],
                format_func=lambda i: next(n["label"] for n in niches if n["id"] == i),
            )
            limit = st.slider("Max leads", 5, 25, 10)
            auto_exp = st.checkbox("Auto experience pitches (top 5)", value=True)
            analyze_ads = st.checkbox("Run ads intelligence", value=True)
            use_llm_ads = st.checkbox("Deep ads via Gemini (slower)", value=False)
            drop_chains = st.checkbox("Exclude branded chains", value=True)

        if st.button("🚀 Run full pipeline", type="primary", use_container_width=True):
            with st.spinner("Discover → Qualify → Ads → Score → Sheets…"):
                try:
                    result = run_full_pipeline(
                        region=region,
                        city=city,
                        niche=niche,
                        limit=limit,
                        auto_experience=auto_exp,
                        drop_chains=drop_chains,
                        analyze_ads=analyze_ads,
                        use_llm_ads=use_llm_ads,
                        sync_sheets=True,
                    )
                    st.success(result["summary"])
                    if result.get("sheets"):
                        st.caption(f"Sheets: {result['sheets']}")
                    if result.get("errors"):
                        for e in result["errors"]:
                            st.caption(f"• {e}")
                    if result["leads"]:
                        cols = [
                            c
                            for c in [
                                "business_name",
                                "niche",
                                "runs_ads",
                                "ad_style",
                                "ad_platforms",
                                "ad_topics",
                                "lead_score",
                                "score_breakdown",
                                "status",
                            ]
                        ]
                        st.dataframe(
                            pd.DataFrame([l.model_dump() for l in result["leads"]])[cols],
                            use_container_width=True,
                            hide_index=True,
                        )
                except Exception as e:
                    st.error(str(e))

    with tab2:
        city = st.text_input("City", value="Lucknow", key="d_city")
        country = st.text_input("Country", value="India", key="d_country")
        niches = suggest_niches()
        niche = st.selectbox(
            "Niche",
            options=[n["id"] for n in niches],
            format_func=lambda i: next(n["label"] for n in niches if n["id"] == i),
            key="d_niche",
        )
        limit = st.slider("Limit", 3, 20, 8, key="d_limit")
        if st.button("Run Discover", type="primary"):
            with st.spinner("Discovering…"):
                try:
                    leads = search_leads(city, country, niche, limit=limit)
                    st.success(f"{len(leads)} leads")
                    if leads:
                        st.dataframe(
                            pd.DataFrame([l.model_dump() for l in leads]),
                            use_container_width=True,
                            hide_index=True,
                        )
                except Exception as e:
                    st.error(str(e))

    with tab3:
        url = st.text_input("URL")
        c1, c2, c3 = st.columns(3)
        city = c1.text_input("City", key="u_city")
        country = c2.text_input("Country", key="u_country")
        niche = c3.selectbox("Niche", [n["id"] for n in suggest_niches()], key="u_niche")
        mode = st.radio("Action", ["Extract many shops", "Enrich one shop"], horizontal=True)
        if st.button("Run URL agent", type="primary"):
            if not url:
                st.warning("Enter URL")
            else:
                with st.spinner("Scraping…"):
                    try:
                        if mode.startswith("Extract"):
                            leads = extract_leads_from_url(
                                url, city=city, country=country, niche=niche
                            )
                            st.success(f"{len(leads)} extracted")
                            if leads:
                                st.dataframe(
                                    pd.DataFrame([l.model_dump() for l in leads]),
                                    use_container_width=True,
                                    hide_index=True,
                                )
                        else:
                            lead = enrich_lead_from_url(url)
                            st.json(lead.model_dump())
                    except Exception as e:
                        st.error(str(e))

    with tab4:
        title = st.text_input("Task title")
        task_type = st.selectbox(
            "Type",
            ["custom", "outreach", "whatsapp_manual", "meeting", "crm_sync", "ads_check"],
        )
        details = st.text_area("Details")
        if st.button("Queue task"):
            add_task(
                AgentTask(
                    task_type=task_type,
                    title=title or "Untitled",
                    status="pending",
                    params={"details": details},
                )
            )
            st.success("Queued")


def page_score_guide():
    st.subheader("🧮 Lead score — every factor explained")
    st.markdown(
        """
Score is **0–100**. Branded chains are forced to **0**.

### Highest value pattern for your agency
**Independent shop + PRODUCT ads on Instagram/Facebook/Google + weak/no website**  
→ they already pay to show products, but lack a conversion experience you can sell.
"""
    )
    st.dataframe(pd.DataFrame(SCORE_FACTOR_GUIDE), use_container_width=True, hide_index=True)

    st.markdown("#### Live average from your current leads")
    df = leads_dataframe()
    if df.empty:
        st.caption("No leads loaded yet.")
        return
    st.write(f"Average score: **{int(df['lead_score'].mean())}** · Max: **{int(df['lead_score'].max())}**")
    if "ad_style" in df.columns:
        st.markdown("#### Scores by ad style")
        tmp = df.copy()
        tmp["ad_style"] = tmp["ad_style"].fillna("none")
        g = tmp.groupby("ad_style")["lead_score"].agg(["count", "mean"]).reset_index()
        g["mean"] = g["mean"].round(1)
        st.dataframe(g, use_container_width=True, hide_index=True)


def page_sheets():
    st.subheader("☁️ Google Sheets CRM (free permanent storage)")
    sh = sheets_status()
    st.write(f"**Connected:** {'✅ Yes' if sh['enabled'] else '❌ No'}")
    st.write(f"**Worksheet name:** `{sh['worksheet']}`")

    st.markdown(
        """
### One-time free setup (phone OK)

1. Create a Google Sheet → copy the **Sheet ID** from the URL  
   `https://docs.google.com/spreadsheets/d/ **SHEET_ID** /edit`
2. Google Cloud Console (free) → create project → enable **Google Sheets API** + **Google Drive API**
3. **Service account** → Create key → JSON download  
4. Share your Sheet with the service account email (`...@...iam.gserviceaccount.com`) as **Editor**
5. Paste into Streamlit Secrets:

```toml
GOOGLE_SHEET_ID = "your_sheet_id"
GOOGLE_SHEET_WORKSHEET = "Leads"
SHEETS_AUTO_SYNC = "true"

# paste the whole JSON as a multiline string OR nested table:
GOOGLE_SERVICE_ACCOUNT_JSON = '''
{ ... full json ... }
'''
```

Every `upsert` / pipeline run will store **all lead fields** including:
`lead_score`, `score_breakdown`, `score_factors`, ads platforms/topics/style.
"""
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("⬆️ Push local → Sheets", type="primary", use_container_width=True):
            try:
                res = push_leads_to_sheets(load_leads())
                st.success(res)
            except Exception as e:
                st.error(str(e))
    with c2:
        if st.button("⬇️ Pull Sheets → local", use_container_width=True):
            try:
                leads = pull_leads_from_sheets()
                save_leads(leads)
                st.success(f"Pulled {len(leads)} leads")
                st.rerun()
            except Exception as e:
                st.error(str(e))
    with c3:
        if st.button("🔄 Merge both ways", use_container_width=True):
            try:
                res = sync_local_and_sheets(load_leads(), direction="both")
                st.success(res)
                st.rerun()
            except Exception as e:
                st.error(str(e))

    if st.button("📣 Re-score ALL leads + ads heuristic + push Sheets"):
        leads = load_leads()
        leads = enrich_ads_batch(leads, use_llm=False, save=True)
        try:
            if sh["enabled"]:
                push_leads_to_sheets(load_leads())
        except Exception as e:
            st.warning(f"Sheets push: {e}")
        st.success(f"Re-scored {len(leads)} leads")
        st.rerun()


def page_experience():
    st.subheader("✨ Experience proposals")
    props = load_proposals()
    if not props:
        st.info("No proposals yet.")
        return
    df = pd.DataFrame([p.model_dump() for p in props])
    st.dataframe(
        df[["id", "business_name", "niche", "package_name", "headline", "created_at"]],
        use_container_width=True,
        hide_index=True,
    )
    pid = st.selectbox("Open proposal", df["id"].tolist())
    prop = next(p for p in props if p.id == pid)
    st.markdown(f"### {prop.headline}")
    st.write(prop.summary)
    for p in prop.pillars:
        st.write(f"• {p}")
    st.text_area("WhatsApp", prop.outreach_whatsapp, height=180)
    st.text_area("Email", prop.outreach_email, height=200)


def page_tasks():
    st.subheader("✅ Tasks")
    tasks = load_tasks()
    if not tasks:
        st.info("No tasks yet.")
        return
    df = pd.DataFrame([t.model_dump() for t in tasks])
    st.dataframe(
        df[["id", "task_type", "title", "status", "result_summary", "created_at"]],
        use_container_width=True,
        hide_index=True,
    )
    tid = st.selectbox("Task id", df["id"].tolist())
    new_status = st.selectbox("Status", ["pending", "running", "done", "failed", "cancelled"])
    note = st.text_input("Result note")
    if st.button("Update task"):
        update_task(tid, status=new_status, result_summary=note or None)
        st.success("Updated")
        st.rerun()


def page_settings():
    st.subheader("⚙️ Settings · FREE stack")
    s = get_settings()
    sh = sheets_status()
    st.json(
        {
            "scraper_mode": s["scraper_mode"],
            "llm_model": s["llm_model"],
            "llm_key_present": bool(s["llm_api_key"]),
            "sheets": sh,
            "agency_name": s["agency_name"],
            "sheets_auto_sync": s.get("sheets_auto_sync"),
        }
    )
    st.markdown(
        """
### Secrets template (Streamlit Cloud)

```toml
SCRAPER_MODE = "open_source"
GEMINI_API_KEY = "free_key"
LLM_MODEL = "google_genai/gemini-2.0-flash"
DASHBOARD_PASSWORD = "strong-password"
AGENCY_NAME = "Your Web Agency"
AGENCY_TAGLINE = "Digital experiences for independent shops"
AGENCY_WEBSITE = "https://your-agency.com"
AGENCY_EMAIL = "hello@your-agency.com"
AGENCY_WHATSAPP = "+91XXXXXXXXXX"

GOOGLE_SHEET_ID = "...."
GOOGLE_SHEET_WORKSHEET = "Leads"
SHEETS_AUTO_SYNC = "true"
GOOGLE_SERVICE_ACCOUNT_JSON = '''{...}'''
```

### Demo (zero keys)
```toml
SCRAPER_MODE = "demo"
DASHBOARD_PASSWORD = "demo"
```
"""
    )
    st.warning(
        "Legal: public business data only. Respect platform Terms when inspecting ads/social. "
        "No spam. India DPDP / GDPR / CCPA where applicable."
    )


def main():
    inject_css()
    if not check_password():
        return
    settings = get_settings()
    with st.sidebar:
        st.markdown("## 🏪 Lead Agent")
        st.caption(settings.get("agency_name") or "Independent shop agency")
        page = st.radio(
            "Navigate",
            [
                "Overview",
                "Leads",
                "Agents",
                "Score guide",
                "Google Sheets",
                "Experience",
                "Tasks",
                "Settings",
            ],
            label_visibility="collapsed",
        )
        st.divider()
        h = health_check()
        sh = sheets_status()
        st.caption(f"Mode `{h['scraper_mode']}`")
        st.caption("Sheets ✅" if sh["enabled"] else "Sheets ❌")
        if st.button("Log out"):
            st.session_state["authenticated"] = False
            st.rerun()

    st.title("Independent Shop Lead Agent")
    st.caption(
        "Product-ad shops score highest · Transparent factors · Free Google Sheets CRM"
    )

    {
        "Overview": page_overview,
        "Leads": page_leads,
        "Agents": page_agents,
        "Score guide": page_score_guide,
        "Google Sheets": page_sheets,
        "Experience": page_experience,
        "Tasks": page_tasks,
        "Settings": page_settings,
    }[page]()


if __name__ == "__main__":
    main()
