# 🏪 Independent Shop Lead Agent

**Free, open-source multi-agent system** for website / digital-experience agencies that sell to **independent** shops:

| Niche | Experience you sell |
|-------|---------------------|
| ☕ Cafés & bakery-cafés | QR menus, reservations, Instagram→site, loyalty |
| 💎 Independent jewellers | Bridal catalogues, appointments, trust story |
| 👗 Clothing boutiques / multi-brand apparel | Lookbooks, category grids, WhatsApp stock check |
| 👟 Independent shoe stores | Footwear windows, size guides, seasonal offers |
| 🛒 Multi-product / variety retail | Department nav, offers, neighborhood hub site |

### Not your customer
National/global **branded chains** and mono-brand flagships (Starbucks, Zara, Tanishq, Bata exclusive, Nike mono-store, big hypermarkets…) are **auto-detected and excluded**.

### Not only “shops without a website”
The scorer and **Experience Agent** also target shops with **poor/average** sites that need a modern customer experience.

---

## 100% free stack

| Layer | Tech | Cost |
|-------|------|------|
| Scraping AI | [ScrapeGraphAI](https://github.com/ScrapeGraphAI/Scrapegraph-ai) (MIT, open source) | Free |
| LLM | Google **Gemini** free tier (or Groq free) | Free |
| Dashboard | Streamlit | Free |
| Hosting | Streamlit Community Cloud | Free |
| Storage | JSON + CSV + **Google Sheets** | Free |

No paid OpenAI required. No paid ScrapeGraph cloud required.

```
SCRAPER_MODE=open_source   # free library
GEMINI_API_KEY=...         # free from aistudio.google.com
```

Or explore the UI with **zero keys**:

```
SCRAPER_MODE=demo
```

---

## Multi-agent architecture

```
┌────────────┐   ┌────────────┐   ┌──────────────┐   ┌─────────────┐
│  Discover  │ → │  Qualify   │ → │  Experience  │ → │  Dashboard  │
│ ScrapeGraph│   │ chain filter│   │ packages +   │   │ control +   │
│ Search/URL │   │ variety ICP │   │ outreach     │   │ manual CRM  │
└────────────┘   └────────────┘   └──────────────┘   └─────────────┘
         ▲                                                    │
         └──────────── Tasks queue (future bots) ─────────────┘
```

| Agent | Job |
|-------|-----|
| **Discover** | Find independent shops via ScrapeGraphAI Search/Smart scrape |
| **Qualify** | Drop chains, detect multi-brand/variety |
| **Ads intel** | Detect IG/FB/Google ads + topics; **product ads = highest score** |
| **Scoring** | Transparent 0–100 with every factor explained |
| **Experience** | Recommend package (Starter / Pro / Growth) + WhatsApp/email |
| **Sheets sync** | Store all leads + scores + ads fields in free Google Sheets |
| **Orchestrator** | Runs full pipeline + logs tasks |
| **You (human)** | Approve, message owners, mark won/lost |

### Scoring highlight
Independent shop **advertising products** on Instagram/Facebook/Google (especially with weak/no website) ranks at the top. Full table: `docs/SCORE_AND_SHEETS.md` and dashboard **Score guide**.

---

## Quick start (computer or Codespaces)

```bash
git clone https://github.com/parashoqrshop1/Lead-agent.git
cd Lead-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # needed for open_source live scrape
cp .env.example .env          # add GEMINI_API_KEY
python scripts/seed_demo_leads.py
streamlit run dashboard/app.py
```

Open http://localhost:8501 — password from `.env` (`DASHBOARD_PASSWORD`).

---

## Phone deploy (Streamlit Cloud)

See **[PHONE_SETUP.md](./PHONE_SETUP.md)** — ~15 minutes on mobile browser.

Main file path: `dashboard/app.py`  
Repo: `parashoqrshop1/Lead-agent`

---

## Project layout

```
Lead-agent/
├── agents/
│   ├── scraper_agent.py     # Discover (ScrapeGraphAI / demo)
│   ├── qualify_agent.py     # Chain filter + independence scoring
│   ├── experience_agent.py  # Packages + outreach
│   ├── orchestrator.py      # Full pipeline
│   ├── lead_schema.py       # Models + prompts
│   └── storage.py           # JSON/CSV persistence
├── config/
│   ├── niches.py            # ICP, packages, blocklist
│   └── settings.py          # Free env config
├── dashboard/app.py         # Control panel
├── scripts/seed_demo_leads.py
├── PHONE_SETUP.md
└── requirements.txt
```

---

## Dashboard map

| Page | Control |
|------|---------|
| Overview | KPIs, niche mix, free-stack health |
| Leads | Filter independent shops, scores, export |
| Agents | Full pipeline / discover / URL / tasks |
| Experience | Saved proposals + copy outreach |
| Tasks | Manual + agent job board |
| Settings | Secrets help + ICP rules |

---

## Environment

| Variable | Default | Notes |
|----------|---------|-------|
| `SCRAPER_MODE` | `open_source` | `demo` \| `open_source` \| `cloud_api` |
| `GEMINI_API_KEY` | — | Free key recommended |
| `LLM_MODEL` | `google_genai/gemini-2.0-flash` | Free Flash |
| `GROQ_API_KEY` | — | Optional free backup |
| `DASHBOARD_PASSWORD` | `change-me-now` | Change before public URL |
| `AGENCY_*` | samples | Used in outreach |

---

## Legal

- Public business data only; respect robots.txt & site Terms  
- India DPDP / GDPR / CCPA where applicable  
- No spam — personalized B2B outreach to independent owners  
- You are responsible for how scraped data is used  

ScrapeGraphAI library: MIT — https://github.com/ScrapeGraphAI/Scrapegraph-ai  

---

## Roadmap hooks (still free)

- Google Sheets persistence (survive Streamlit restarts)  
- WhatsApp Cloud API / email worker reading `tasks`  
- Cron re-score + enrich  
- Hindi UI pack for UP teams  

---

MIT License © 2026 — built for agencies serving **independent** retail, not chains.
