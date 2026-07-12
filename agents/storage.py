"""Persist leads, tasks, proposals, activity as JSON/CSV (free, no DB required)."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Iterable, List, Optional

import pandas as pd

from agents.lead_schema import AgentTask, ExperienceProposal, ShopLead, utc_now
from config.settings import (
    ACTIVITY_LOG,
    LEADS_CSV,
    LEADS_JSON,
    PROPOSALS_JSON,
    TASKS_JSON,
)

_lock = threading.Lock()


def _ensure_files() -> None:
    LEADS_JSON.parent.mkdir(parents=True, exist_ok=True)
    for path, default in [
        (LEADS_JSON, "[]"),
        (TASKS_JSON, "[]"),
        (PROPOSALS_JSON, "[]"),
        (ACTIVITY_LOG, ""),
    ]:
        if not path.exists():
            path.write_text(default, encoding="utf-8")


def log_activity(event: str, details: Optional[dict] = None) -> None:
    _ensure_files()
    row = {"ts": utc_now(), "event": event, "details": details or {}}
    with _lock:
        with ACTIVITY_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_leads() -> List[ShopLead]:
    _ensure_files()
    with _lock:
        raw = json.loads(LEADS_JSON.read_text(encoding="utf-8") or "[]")
    leads: List[ShopLead] = []
    for item in raw:
        try:
            leads.append(ShopLead.model_validate(item))
        except Exception:
            continue
    return leads


def save_leads(leads: Iterable[ShopLead]) -> None:
    _ensure_files()
    data = [l.model_dump() for l in leads]
    with _lock:
        LEADS_JSON.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        if data:
            pd.DataFrame(data).to_csv(LEADS_CSV, index=False)
        else:
            LEADS_CSV.write_text("", encoding="utf-8")


def _dedupe_key(lead: ShopLead) -> str:
    name = (lead.business_name or "").strip().lower()
    city = (lead.city or "").strip().lower()
    phone = (lead.phone or lead.whatsapp or "").strip()
    return f"{name}|{city}|{phone}"


def _merge_lead(old: ShopLead, new: ShopLead) -> ShopLead:
    data = old.model_dump()
    for k, v in new.model_dump().items():
        if k in ("id", "created_at"):
            continue
        if v in (None, "", [], {}):
            continue
        if k == "lead_score":
            data[k] = max(int(data.get(k) or 0), int(v or 0))
        else:
            data[k] = v
    data["updated_at"] = utc_now()
    merged = ShopLead.model_validate(data)
    merged.recompute_score()
    return merged


def upsert_leads(new_leads: List[ShopLead]) -> tuple[int, int]:
    existing = load_leads()
    index = {_dedupe_key(l): i for i, l in enumerate(existing)}
    added = updated = 0
    for lead in new_leads:
        lead.recompute_score()
        lead.updated_at = utc_now()
        key = _dedupe_key(lead)
        if key in index and key != "||":
            existing[index[key]] = _merge_lead(existing[index[key]], lead)
            updated += 1
        else:
            if not lead.created_at:
                lead.created_at = utc_now()
            existing.append(lead)
            index[key] = len(existing) - 1
            added += 1
    save_leads(existing)
    log_activity("upsert_leads", {"added": added, "updated": updated})
    # Auto-push to Google Sheets when configured (free persistence)
    try:
        from config.settings import get_settings

        if get_settings().get("sheets_auto_sync"):
            from agents.sheets_store import sheets_enabled, push_leads_to_sheets

            if sheets_enabled():
                push_leads_to_sheets(existing)
    except Exception as e:
        log_activity("sheets_auto_sync_error", {"error": str(e)})
    return added, updated


def update_lead(lead_id: str, **fields: Any) -> Optional[ShopLead]:
    leads = load_leads()
    for i, lead in enumerate(leads):
        if lead.id == lead_id:
            data = lead.model_dump()
            data.update({k: v for k, v in fields.items() if v is not None})
            data["updated_at"] = utc_now()
            updated = ShopLead.model_validate(data)
            updated.recompute_score()
            leads[i] = updated
            save_leads(leads)
            log_activity("update_lead", {"id": lead_id, "fields": list(fields.keys())})
            return updated
    return None


def delete_lead(lead_id: str) -> bool:
    leads = load_leads()
    new = [l for l in leads if l.id != lead_id]
    if len(new) == len(leads):
        return False
    save_leads(new)
    log_activity("delete_lead", {"id": lead_id})
    return True


def leads_dataframe() -> pd.DataFrame:
    leads = load_leads()
    if not leads:
        return pd.DataFrame()
    return pd.DataFrame([l.model_dump() for l in leads])


def load_tasks() -> List[AgentTask]:
    _ensure_files()
    with _lock:
        raw = json.loads(TASKS_JSON.read_text(encoding="utf-8") or "[]")
    out: List[AgentTask] = []
    for item in raw:
        try:
            out.append(AgentTask.model_validate(item))
        except Exception:
            continue
    return out


def save_tasks(tasks: Iterable[AgentTask]) -> None:
    _ensure_files()
    with _lock:
        TASKS_JSON.write_text(
            json.dumps([t.model_dump() for t in tasks], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def add_task(task: AgentTask) -> AgentTask:
    tasks = load_tasks()
    tasks.insert(0, task)
    save_tasks(tasks)
    log_activity("add_task", {"id": task.id, "type": task.task_type})
    return task


def update_task(task_id: str, **fields: Any) -> Optional[AgentTask]:
    tasks = load_tasks()
    for i, t in enumerate(tasks):
        if t.id == task_id:
            data = t.model_dump()
            data.update(fields)
            data["updated_at"] = utc_now()
            tasks[i] = AgentTask.model_validate(data)
            save_tasks(tasks)
            return tasks[i]
    return None


def load_proposals() -> List[ExperienceProposal]:
    _ensure_files()
    with _lock:
        raw = json.loads(PROPOSALS_JSON.read_text(encoding="utf-8") or "[]")
    out = []
    for item in raw:
        try:
            out.append(ExperienceProposal.model_validate(item))
        except Exception:
            continue
    return out


def save_proposal(prop: ExperienceProposal) -> ExperienceProposal:
    props = load_proposals()
    props.insert(0, prop)
    with _lock:
        PROPOSALS_JSON.write_text(
            json.dumps([p.model_dump() for p in props], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    log_activity("save_proposal", {"id": prop.id, "lead_id": prop.lead_id})
    return prop


def recent_activity(limit: int = 50) -> List[dict]:
    _ensure_files()
    lines = ACTIVITY_LOG.read_text(encoding="utf-8").strip().splitlines()
    rows = []
    for line in lines[-limit:]:
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    rows.reverse()
    return rows


def export_leads_excel(path: Optional[Path] = None) -> Path:
    path = path or (LEADS_CSV.parent / "leads_export.xlsx")
    df = leads_dataframe()
    if df.empty:
        df = pd.DataFrame(columns=["business_name", "niche", "phone", "city", "status"])
    df.to_excel(path, index=False)
    return path
