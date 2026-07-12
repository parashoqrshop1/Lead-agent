"""Streamlit entrypoint — single set_page_config, then full dashboard."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

st.set_page_config(
    page_title="Lead Agent",
    page_icon="🏪",
    layout="centered",
    initial_sidebar_state="collapsed",
)

def main() -> None:
    try:
        from dashboard.full_app import main as full_main
        full_main()
    except Exception as e:
        st.error("Dashboard failed to load")
        st.exception(e)

if __name__ == "__main__":
    main()
