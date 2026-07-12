# Switch from DEMO to REAL leads

## 1) Free Gemini API key
1. Open https://aistudio.google.com/apikey
2. Create API key
3. Copy it

## 2) Streamlit Secrets
App → ⋮ → Settings → Secrets:

```toml
SCRAPER_MODE = "light"
GEMINI_API_KEY = "YOUR_KEY_HERE"
LLM_MODEL = "gemini-2.0-flash"
DASHBOARD_PASSWORD = "your-strong-password"
AGENCY_NAME = "Your Web Agency"
AGENCY_WHATSAPP = "+91XXXXXXXXXX"
AGENCY_EMAIL = "hello@your-agency.com"
AGENCY_WEBSITE = "https://your-agency.com"
```

Save.

## 3) Reboot app
Manage app → Reboot → wait until Running.

## 4) Run real local hunt
1. Login
2. Find leads → **Local niches**
3. City: Akbarpur (or your town)
4. Niches: jeweller, clothing, cafe, shoes, multi_retail
5. Target leads: 40–80
6. Scan local markets: ON
7. Hunt local niche leads

## 5) Use leads
- Open Leads
- Prefer score ≥ 70 + Instagram/Facebook
- Copy WhatsApp pitch
- Status → contacted

## Notes
- Real mode finds **public** info only (phone when listed, social when listed).
- Duplicates are auto-merged.
- No heavy Google SDK required (Gemini via plain HTTP).
