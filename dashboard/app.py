"""
Boot-safe Streamlit entrypoint for Community Cloud.
Loads full dashboard only after process is alive.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

st.set_page_config(page_title="Lead Agent", page_icon="🏪", layout="centered")


def main() -> None:
    # Minimal first paint — proves process is alive
    st.write("### 🏪 Lead Agent")
    st.write("Starting…")

    # Immediately load full app (no extra click friction)
    try:
        from dashboard.full_app import main as full_main

        full_main()
    except Exception as e:
        st.error("Full dashboard failed to load")
        st.exception(e)
        st.markdown(
            """
### Quick checks
1. Reboot app
2. Secrets:
```toml
SCRAPER_MODE = "demo"
DASHBOARD_PASSWORD = "demo123"
```
3. Then for REAL:
```toml
SCRAPER_MODE = "light"
GEMINI_API_KEY = "your_key"
```
"""
        )


if __name__ == "__main__":
    main()
