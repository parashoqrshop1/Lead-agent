"""Seed realistic independent-shop demo leads (and one chain trap)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.qualify_agent import qualify_batch
from agents.scraper_agent import demo_leads
from agents.storage import save_leads


def main() -> None:
    batch = []
    batch += demo_leads("Akbarpur", "India", "clothing", 4)
    batch += demo_leads("Lucknow", "India", "cafe", 3)
    batch += demo_leads("Jaipur", "India", "jeweller", 3)
    batch += demo_leads("Austin", "United States", "shoes", 3)
    batch += demo_leads("Pune", "India", "multi_retail", 3)
    # de-dupe by name
    seen = set()
    unique = []
    for l in qualify_batch(batch):
        k = l.business_name.lower()
        if k not in seen:
            seen.add(k)
            unique.append(l)
    save_leads(unique)
    print(f"Seeded {len(unique)} demo leads (independent ICP + chain traps)")


if __name__ == "__main__":
    main()
