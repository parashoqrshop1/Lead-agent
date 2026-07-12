# 📱 Phone setup — free Independent Shop Lead Agent

Repo: https://github.com/parashoqrshop1/Lead-agent

## 1) Free accounts
- [ ] GitHub (you have the repo)
- [ ] Streamlit Cloud → https://share.streamlit.io (login with GitHub)
- [ ] **Free Gemini key** → https://aistudio.google.com/apikey

## 2) Deploy from phone
1. Open Streamlit Cloud → **New app**
2. Repository: `parashoqrshop1/Lead-agent`
3. Branch: `main`
4. Main file: `dashboard/app.py`
5. Secrets → paste:

### Live free scraping
```toml
SCRAPER_MODE = "open_source"
GEMINI_API_KEY = "YOUR_FREE_GEMINI_KEY"
LLM_MODEL = "google_genai/gemini-2.0-flash"
DASHBOARD_PASSWORD = "strong-password"
AGENCY_NAME = "Your Web Agency"
AGENCY_TAGLINE = "Digital experiences for independent shops"
AGENCY_WEBSITE = "https://your-agency.com"
AGENCY_EMAIL = "hello@your-agency.com"
AGENCY_WHATSAPP = "+91XXXXXXXXXX"
```

### Zero-key demo first (explore UI)
```toml
SCRAPER_MODE = "demo"
DASHBOARD_PASSWORD = "demo"
AGENCY_NAME = "Your Web Agency"
```

6. Deploy → open the `.streamlit.app` link → login

## 3) First run
1. **Agents → Full Pipeline**
2. Niche: Café / Jeweller / Clothing / Shoes / Multi-retail
3. City: e.g. Lucknow or Akbarpur
4. Run → **Leads** → sort by score
5. Generate **Experience proposal** → copy WhatsApp → message shop owner

## 4) What the agents sell
Not only “no website” — also digital **experience upgrades**:
- QR menus (cafés)
- Bridal catalogues + appointments (jewellers)
- Lookbooks + multi-brand grids (clothing/shoes)
- Department + WhatsApp order lists (variety retail)

## 5) Auto-excluded
Starbucks, Zara, H&M, Tanishq, Kalyan, Bata flagships, Nike mono-stores, big supermarket chains, etc.

## 6) Google Sheets (permanent free CRM) — do this
1. Create a Google Sheet in Drive
2. Copy Sheet ID from URL (`/d/SHEET_ID/edit`)
3. [Google Cloud Console](https://console.cloud.google.com) (free) → new project
4. Enable **Google Sheets API** + **Google Drive API**
5. **IAM → Service accounts → Create** → Keys → JSON
6. Open the JSON, copy the `client_email` → Share your Sheet with that email as **Editor**
7. Add to Streamlit Secrets:

```toml
GOOGLE_SHEET_ID = "your_sheet_id_here"
GOOGLE_SHEET_WORKSHEET = "Leads"
SHEETS_AUTO_SYNC = "true"
GOOGLE_SERVICE_ACCOUNT_JSON = """
paste-full-json-here
"""
```

8. Dashboard → **Google Sheets** → Push local → Sheets  
   Columns include `lead_score`, `score_breakdown`, `score_factors`, ads fields.

## 7) Score logic (product ads win)
See dashboard page **Score guide** or `docs/SCORE_AND_SHEETS.md`.

Highest leads = independent shops **showing products in Instagram/Facebook/Google ads** especially with weak/no website.

## 8) Tips
- Sheets = durable storage (Streamlit free disk can wipe)
- Never commit real keys / service account JSON
- Change dashboard password
