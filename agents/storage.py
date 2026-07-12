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
            leads.append(ShopLead.from_any(item))
        except Exception:
            continue
    return leads


def save_leads(leads: Iterable[ShopLead]) -> None:
    _ensure_files()
    # Always persist a de-duplicated list
    unique = dedupe_leads_list(list(leads))
    data = [l.model_dump() for l in unique]
    with _lock:
        LEADS_JSON.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        if data:
            pd.DataFrame(data).to_csv(LEADS_CSV, index=False)
        else:
            LEADS_CSV.write_text("", encoding="utf-8")


def _norm_text(value: Optional[str]) -> str:
    import re

    text = (value or "").strip().lower()
    text = re.sub(r"[^\w\s+]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _norm_phone(value: Optional[str]) -> str:
    import re

    digits = re.sub(r"\D+", "", value or "")
    # Compare on last 10 digits (handles +91 / 0 prefixes)
    return digits[-10:] if len(digits) >= 10 else digits


def _core_business_name(name: str) -> str:
    """Strip city/area suffixes so variants of the same shop collapse."""
    import re

    text = _norm_text(name)
    text = re.sub(r"\([^)]*\)", " ", text)
    # split on any dash type (em/en/hyphen) with optional spaces
    text = re.split(r"\s*[\u2014\u2013\-–—]\s*", text)[0]
    # cut common location tail words if present after comma
    text = text.split(",")[0]
    for noise in (
        " private limited",
        " pvt ltd",
        " pvt. ltd.",
        " pvt. ltd",
        " ltd.",
        " ltd",
        " llc",
        " inc.",
        " inc",
    ):
        if text.endswith(noise) and len(text) > len(noise) + 3:
            text = text[: -len(noise)].strip()
    return re.sub(r"\s+", " ", text).strip()


def _dedupe_keys(lead: ShopLead) -> List[str]:
    """
    Multiple keys for the same shop.
    Match if ANY key collides → treat as same lead (merge, don't duplicate).
    """
    keys: List[str] = []
    name = _core_business_name(lead.business_name or "")
    full_name = _norm_text(lead.business_name or "")
    city = _norm_text(lead.city or "")
    phone = _norm_phone(lead.phone or lead.whatsapp)
    website = (
        _norm_text(lead.website or "")
        .replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
        .rstrip("/")
    )
    instagram = (
        _norm_text(lead.instagram or "")
        .replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
        .rstrip("/")
    )
    # normalize ig to handle url or @handle
    if "instagram.com/" in instagram:
        instagram = instagram.split("instagram.com/")[-1].split("?")[0].strip("/")

    if phone and len(phone) >= 8:
        keys.append(f"phone:{phone}")
    if website and website not in ("", "example-outdated-shop.blogspot.com") and "example-outdated-shop" not in website:
        keys.append(f"web:{website}")
    # skip placeholder demo social handles
    if (
        instagram
        and "example_independent" not in instagram
        and instagram not in ("", "instagram.com")
    ):
        keys.append(f"ig:{instagram}")

    # Strong identity: core name + city
    if name and city and len(name) >= 4:
        keys.append(f"namecity:{name}|{city}")
    # Full normalized name + city
    if full_name and city and len(full_name) >= 4:
        keys.append(f"fullnamecity:{full_name}|{city}")
    # Name + phone
    if name and phone and len(name) >= 4:
        keys.append(f"namephone:{name}|{phone}")
    # Core name alone when distinctive enough (helps missing-phone variants in same import batch)
    # Only use with city already covered; add soft key for exact core name in same city already done.
    # Extra soft key: first 3 tokens of core name + city (handles minor wording differences)
    if name and city:
        tokens = name.split()
        if len(tokens) >= 2:
            keys.append(f"softname:{' '.join(tokens[:3])}|{city}")

    if not keys and full_name:
        keys.append(f"nameonly:{full_name}|{city}")
    return keys


def _merge_lead(old: ShopLead, new: ShopLead) -> ShopLead:
    data = old.model_dump()
    for k, v in new.model_dump().items():
        if k in ("id", "created_at"):
            continue
        if v in (None, "", [], {}):
            continue
        if k == "lead_score":
            data[k] = max(int(data.get(k) or 0), int(v or 0))
        elif k in ("score_breakdown", "score_factors"):
            # keep higher-score breakdown
            if int(new.lead_score or 0) >= int(old.lead_score or 0):
                data[k] = v
        else:
            # prefer non-empty richer values; don't overwrite good data with weaker placeholders
            old_v = data.get(k)
            if old_v in (None, "", [], {}):
                data[k] = v
            elif k in (
                "notes",
                "pain_points",
                "ads_evidence",
                "ad_topics",
                "independence_signals",
            ):
                # merge text snippets
                if str(v) not in str(old_v):
                    data[k] = f"{old_v} | {v}"
            else:
                data[k] = v
    data["updated_at"] = utc_now()
    try:
        merged = ShopLead.from_any(data)
    except Exception:
        merged = ShopLead.model_validate(data)
    merged.recompute_score()
    return merged


def dedupe_leads_list(leads: List[ShopLead]) -> List[ShopLead]:
    """Collapse an in-memory list so no repeated shops remain."""
    unique: List[ShopLead] = []
    key_to_idx: dict[str, int] = {}

    for lead in leads:
        try:
            lead = ShopLead.from_any(lead)
        except Exception:
            continue
        # Prefer keeping higher-score / more complete record as base when merging later
        keys = _dedupe_keys(lead)
        match_idx = None
        for k in keys:
            if k in key_to_idx:
                match_idx = key_to_idx[k]
                break
        if match_idx is None:
            unique.append(lead)
            idx = len(unique) - 1
            for k in keys:
                key_to_idx[k] = idx
        else:
            unique[match_idx] = _merge_lead(unique[match_idx], lead)
            # Drop stale keys pointing to this idx, then rebind all current keys
            stale = [k for k, i in key_to_idx.items() if i == match_idx]
            for k in stale:
                del key_to_idx[k]
            for k in _dedupe_keys(unique[match_idx]):
                key_to_idx[k] = match_idx

    # Second pass: catch anything still duplicated by soft name+city after merges
    return _second_pass_name_city(unique)


def _second_pass_name_city(leads: List[ShopLead]) -> List[ShopLead]:
    by_key: dict[str, ShopLead] = {}
    order: List[str] = []
    for lead in leads:
        name = _core_business_name(lead.business_name or "")
        city = _norm_text(lead.city or "")
        phone = _norm_phone(lead.phone or lead.whatsapp)
        if phone and len(phone) >= 8:
            key = f"p:{phone}"
        elif name and city:
            key = f"n:{name}|{city}"
        else:
            key = f"i:{lead.id}"
        if key in by_key:
            by_key[key] = _merge_lead(by_key[key], lead)
        else:
            by_key[key] = lead
            order.append(key)
    return [by_key[k] for k in order]


def upsert_leads(new_leads: List[ShopLead]) -> tuple[int, int]:
    """
    Insert or merge leads.
    Same shop (phone / website / instagram / name+city) updates existing row — never duplicates.
    Returns (added, updated).
    """
    existing = dedupe_leads_list(load_leads())
    key_to_idx: dict[str, int] = {}
    for i, lead in enumerate(existing):
        for k in _dedupe_keys(lead):
            key_to_idx[k] = i

    added = updated = 0
    for raw in new_leads:
        try:
            lead = ShopLead.from_any(raw)
        except Exception:
            continue
        lead.recompute_score()
        lead.updated_at = utc_now()
        keys = _dedupe_keys(lead)
        match_idx = None
        for k in keys:
            if k in key_to_idx:
                match_idx = key_to_idx[k]
                break
        if match_idx is not None:
            existing[match_idx] = _merge_lead(existing[match_idx], lead)
            for k in _dedupe_keys(existing[match_idx]):
                key_to_idx[k] = match_idx
            updated += 1
        else:
            if not lead.created_at:
                lead.created_at = utc_now()
            existing.append(lead)
            idx = len(existing) - 1
            for k in keys:
                key_to_idx[k] = idx
            added += 1

    # final safety collapse
    before = len(existing)
    existing = dedupe_leads_list(existing)
    collapsed = before - len(existing)

    save_leads(existing)
    log_activity(
        "upsert_leads",
        {"added": added, "updated": updated, "collapsed": collapsed, "total": len(existing)},
    )
    try:
        from config.settings import get_settings

        if get_settings().get("sheets_auto_sync"):
            from agents.sheets_store import sheets_enabled, push_leads_to_sheets

            if sheets_enabled():
                push_leads_to_sheets(existing)
    except Exception as e:
        log_activity("sheets_auto_sync_error", {"error": str(e)})
    return added, updated


def purge_duplicate_leads() -> dict:
    """One-shot cleanup of already-saved duplicates."""
    before = load_leads()
    after = dedupe_leads_list(before)
    save_leads(after)
    removed = len(before) - len(after)
    log_activity("purge_duplicates", {"before": len(before), "after": len(after), "removed": removed})
    return {"before": len(before), "after": len(after), "removed": removed}


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
    try:
        df.to_excel(path, index=False)
    except Exception:
        # fallback CSV if openpyxl/native issue
        path = path.with_suffix(".csv")
        df.to_csv(path, index=False)
    return path
