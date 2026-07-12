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


def run_hyperlocal_pipeline(
    *,
    region: str,
    city: str,
    niches: List[str],
    limit: int = 40,
    deep_local: bool = True,
    max_localities: int = 8,
    analyze_ads: bool = True,
    drop_chains: bool = True,
    sync_sheets: bool = True,
) -> Dict[str, Any]:
    """Hunt niches in one city/town across local markets. Never returns empty silently."""
    from config.niches import REGIONS
    from config.settings import get_settings
    from agents.storage import dedupe_leads_list

    task = add_task(
        AgentTask(
            task_type="hyperlocal",
            title=f"Hyperlocal niches @ {city}",
            status="running",
            params={
                "city": city,
                "niches": niches,
                "limit": limit,
                "deep_local": deep_local,
                "max_localities": max_localities,
            },
        )
    )
    country = REGIONS.get(region, {}).get("country", "India")
    mode = get_settings().get("scraper_mode", "demo")
    all_leads: List[ShopLead] = []
    errors: List[str] = []
    fallback_demo = False

    try:
        if mode == "demo":
            from agents.light_scrape import hyperlocal_demo_leads

            all_leads = hyperlocal_demo_leads(
                city=city,
                niches=niches,
                country=country or "India",
                per_niche=max(limit, 30),
                save=False,
            )
        else:
            from agents.light_scrape import light_search_leads

            per = max(12, limit // max(1, len(niches) or 1))
            for niche in niches:
                try:
                    found = light_search_leads(
                        city=city,
                        country=country or region,
                        niche=niche,
                        limit=per,
                        save=False,
                        deep_local=deep_local,
                        max_localities=max_localities,
                        queries_per_place=3,
                    )
                    all_leads.extend(found or [])
                except Exception as e:
                    errors.append(f"{niche}: {e}")

            if not all_leads:
                fallback_demo = True
                from agents.light_scrape import hyperlocal_demo_leads

                errors.append(
                    "REAL search returned 0 leads (check GEMINI_API_KEY / network). "
                    "Loaded sample leads so UI is not empty."
                )
                all_leads = hyperlocal_demo_leads(
                    city=city,
                    niches=niches,
                    country=country or "India",
                    per_niche=max(limit, 30),
                    save=False,
                )

        unique = dedupe_leads_list(
            filter_icp(qualify_batch(all_leads), drop_chains=drop_chains)
        )
        if analyze_ads and unique:
            try:
                unique = enrich_ads_batch(unique, use_llm=False, save=False)
                unique = dedupe_leads_list(unique)
            except Exception as e:
                errors.append(f"ads: {e}")

        unique.sort(
            key=lambda l: (
                1 if (l.instagram or l.facebook) else 0,
                1 if (l.ad_style or "").startswith("product") or l.runs_ads else 0,
                l.lead_score or 0,
            ),
            reverse=True,
        )

        if unique:
            added, updated = upsert_leads(unique)
            log_activity(
                "hyperlocal_saved",
                {"added": added, "updated": updated, "total": len(unique)},
            )
        else:
            errors.append("No leads after processing")

        sheets_result = None
        if sync_sheets:
            try:
                from agents.sheets_store import sheets_enabled, push_leads_to_sheets
                from agents.storage import load_leads

                if sheets_enabled():
                    sheets_result = push_leads_to_sheets(load_leads())
            except Exception as e:
                sheets_result = {"ok": False, "error": str(e)}

        social_n = sum(1 for l in unique if l.instagram or l.facebook)
        mode_note = "DEMO samples" if (mode == "demo" or fallback_demo) else "REAL search"
        summary = (
            f"[{mode_note}] {city}: {len(unique)} unique leads "
            f"({social_n} with social) · niches={','.join(niches)}"
        )
        update_task(
            task.id,
            status="done",
            result_summary=summary,
            lead_ids=[l.id for l in unique[:200]],
        )
        log_activity("hyperlocal_done", {"summary": summary, "errors": errors[:5]})
        return {
            "task_id": task.id,
            "leads": unique,
            "count": len(unique),
            "social_count": social_n,
            "errors": errors,
            "sheets": sheets_result,
            "summary": summary,
            "mode": mode,
            "fallback_demo": fallback_demo,
        }
    except Exception as e:
        update_task(task.id, status="failed", error=str(e))
        log_activity("hyperlocal_failed", {"error": str(e)})
        # last-resort non-empty response
        try:
            from agents.light_scrape import hyperlocal_demo_leads

            emergency = hyperlocal_demo_leads(
                city=city or "Akbarpur",
                niches=niches or ["clothing"],
                country="India",
                per_niche=20,
                save=True,
            )
            return {
                "task_id": task.id,
                "leads": emergency,
                "count": len(emergency),
                "social_count": sum(1 for l in emergency if l.instagram or l.facebook),
                "errors": [str(e)],
                "sheets": None,
                "summary": f"[EMERGENCY DEMO] {len(emergency)} leads after error: {e}",
                "mode": mode,
                "fallback_demo": True,
            }
        except Exception as e2:
            raise RuntimeError(f"{e} | emergency also failed: {e2}") from e


def run_bulk_pipeline(
    *,
    region: str,
    cities: List[str],
    niches: List[str],
    limit_per: int = 20,
    analyze_ads: bool = True,
    drop_chains: bool = True,
    sync_sheets: bool = True,
) -> Dict[str, Any]:
    """Run many city×niche campaigns and merge leads for higher volume."""
    from config.niches import REGIONS

    task = add_task(
        AgentTask(
            task_type="bulk_campaign",
            title=f"Bulk: {len(cities)} cities × {len(niches)} niches",
            status="running",
            params={
                "region": region,
                "cities": cities,
                "niches": niches,
                "limit_per": limit_per,
            },
        )
    )
    all_leads: List[ShopLead] = []
    errors: List[str] = []
    country = REGIONS.get(region, {}).get("country", "India")

    try:
        s_mode = None
        try:
            from config.settings import get_settings

            s_mode = get_settings().get("scraper_mode")
        except Exception:
            s_mode = "demo"

        if s_mode == "demo":
            from agents.light_scrape import bulk_demo_leads

            all_leads = bulk_demo_leads(
                cities=cities,
                niches=niches,
                country=country or "India",
                per_combo=limit_per,
                save=False,
            )
        else:
            for city in cities:
                for niche in niches:
                    try:
                        result = run_campaign(
                            region=region,
                            city=city,
                            niche=niche,
                            limit=limit_per,
                            also_search=True,
                            drop_chains=drop_chains,
                        )
                        all_leads.extend(result.get("leads") or [])
                        errors.extend(result.get("errors") or [])
                    except Exception as e:
                        errors.append(f"{city}/{niche}: {e}")

        from agents.storage import dedupe_leads_list

        all_leads = filter_icp(qualify_batch(all_leads), drop_chains=drop_chains)
        unique = dedupe_leads_list(all_leads)

        if analyze_ads and unique:
            unique = enrich_ads_batch(unique, use_llm=False, save=False)
            unique = dedupe_leads_list(unique)

        if unique:
            # upsert merges against existing saved leads too (no repeats)
            upsert_leads(unique)

        sheets_result = None
        if sync_sheets:
            try:
                from agents.sheets_store import sheets_enabled, push_leads_to_sheets
                from agents.storage import load_leads

                if sheets_enabled():
                    sheets_result = push_leads_to_sheets(load_leads())
            except Exception as e:
                sheets_result = {"ok": False, "error": str(e)}

        summary = (
            f"Bulk done: {len(unique)} unique leads from "
            f"{len(cities)} cities × {len(niches)} niches"
        )
        update_task(
            task.id,
            status="done",
            result_summary=summary,
            lead_ids=[l.id for l in unique[:200]],
        )
        return {
            "task_id": task.id,
            "leads": unique,
            "count": len(unique),
            "errors": errors,
            "sheets": sheets_result,
            "summary": summary,
        }
    except Exception as e:
        update_task(task.id, status="failed", error=str(e))
        raise
