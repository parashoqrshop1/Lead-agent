#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env — add free GEMINI_API_KEY from https://aistudio.google.com/apikey"
fi

if grep -q 'SCRAPER_MODE=open_source' .env 2>/dev/null; then
  playwright install chromium || true
fi

python scripts/seed_demo_leads.py || true
streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port "${PORT:-8501}"
