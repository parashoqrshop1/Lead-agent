"""
Multi-agent orchestrator — Discover → Qualify → Ads intel → Experience → Sheets.
All free / open-source.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.ads_agent import enrich_ads_batch
from agents.experience_agent import build_experience_proposal
from agents.lead_schema import AgentTask, ShopLead
from agents.qualify_agent import filter_icp, qualify_batch
from agents.scraper_agent import run_campaign, search_leads
from agents.storage import add_task, log_activity, update_task, upsert_leads


def run_full_pipeline(
    *,
    region: str,
    city: str,
    niche: str,
    limit: int = 10,
    auto_experience: bool = True,
    drop_chains: bool = True,
    analyze_ads: bool = True,
    use_llm_ads: bool = False,
    sync_sheets: bool = True,
) -> Dict[str, Any]:
    """
    1. Discover agent (ScrapeGraphAI / demo)
    2. Qualify agent (independence + chain filter)
    3. Ads agent (Instagram/FB/Google product ads → high score)
    4. Experience agent (packages + outreach) for top leads
    5. Google Sheets sync (when configured)
    """
    task = add_task(
        AgentTask(
            task_type="campaign",
            title=f"Pipeline: {niche} @ {city}",
            status="running",
            params={
                "region": region,
                "city": city,
                "niche": niche,
                "limit": limit,
                "auto_experience": auto_experience,
                "analyze_ads": analyze_ads,
            },
        )
    )
    log_activity("pipeline_start", task.params)

    try:
        result = run_campaign(
            region=region,
            city=city,
            niche=niche,
            limit=limit,
            also_search=True,
            drop_chains=drop_chains,
        )
        leads: List[ShopLead] = result.get("leads") or []
        leads = filter_icp(qualify_batch(leads), drop_chains=drop_chains)

        product_ad_leads = 0
        if analyze_ads and leads:
            leads = enrich_ads_batch(leads, use_llm=use_llm_ads, save=False)
            product_ad_leads = sum(
                1
                for l in leads
                if (l.ad_style or "").lower() in ("product_showcase", "product", "mixed")
                or l.runs_ads
            )

        if leads:
            upsert_leads(leads)  # also auto-pushes Sheets if configured

        sheets_result = None
        if sync_sheets:
            try:
                from agents.sheets_store import sheets_enabled, push_leads_to_sheets
                from agents.storage import load_leads

                if sheets_enabled():
                    sheets_result = push_leads_to_sheets(load_leads())
            except Exception as e:
                sheets_result = {"ok": False, "error": str(e)}

        proposals = []
        if auto_experience:
            top = sorted(leads, key=lambda x: x.lead_score, reverse=True)[: min(5, len(leads))]
            for lead in top:
                if lead.is_branded_chain:
                    continue
                try:
                    prop = build_experience_proposal(lead, use_llm=False)
                    proposals.append(prop.model_dump())
                except Exception as e:
                    log_activity("experience_error", {"lead": lead.id, "error": str(e)})

        summary = (
            f"{result.get('count', len(leads))} independent leads"
            f" | ads-active ~{product_ad_leads}"
            f" | {len(proposals)} experience pitches"
            f" | chains excluded: {result.get('excluded_chains', 0)}"
        )
        if sheets_result and sheets_result.get("ok"):
            summary += f" | sheets total {sheets_result.get('total')}"

        update_task(
            task.id,
            status="done",
            result_summary=summary,
            lead_ids=[l.id for l in leads],
        )
        log_activity("pipeline_done", {"summary": summary})
        return {
            "task_id": task.id,
            "leads": leads,
            "proposals": proposals,
            "count": len(leads),
            "product_ad_leads": product_ad_leads,
            "errors": result.get("errors", []),
            "excluded_chains": result.get("excluded_chains", 0),
            "queries": result.get("queries", []),
            "sheets": sheets_result,
            "summary": summary,
        }
    except Exception as e:
        update_task(task.id, status="failed", error=str(e))
        log_activity("pipeline_failed", {"error": str(e)})
        raise


def run_discover_only(city: str, country: str, niche: str, limit: int = 10) -> List[ShopLead]:
    task = add_task(
        AgentTask(
            task_type="discover",
            title=f"Discover {niche} in {city}",
            status="running",
            params={"city": city, "country": country, "niche": niche},
        )
    )
    try:
        leads = search_leads(city, country, niche, limit=limit)
        update_task(
            task.id,
            status="done",
            result_summary=f"{len(leads)} leads",
            lead_ids=[l.id for l in leads],
        )
        return leads
    except Exception as e:
        update_task(task.id, status="failed", error=str(e))
        raise
