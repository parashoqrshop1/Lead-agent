# Lead score factors + Google Sheets

## Score factors (0–100)

| Factor | Points | Notes |
|--------|--------|-------|
| Branded chain | **0 total** | Excluded from ICP |
| Base | +10 | Any non-chain shop |
| Independent | +15 | Family / boutique / independent |
| Not independent | −20 | Failed checks |
| Product variety high / medium | +12 / +8 | Mixed product kinds |
| Multi-brand inventory | +10 | Multiple labels |
| No website | +14 | Strong web need |
| Poor / average / good website | +11 / +7 / +3 | Experience upgrades still sell |
| **Runs paid ads** | **+12** | Any platform |
| **PRODUCT advertising** | **+20** | Ads show products/collections — **highest boost** |
| Offer / promo ads | +10 | Sale-focused |
| Brand-awareness ads | +5 | Lifestyle only |
| Instagram ads | +6 | Meta/IG |
| Facebook ads | +4 | |
| Google ads | +4 | |
| Other platforms | +3 | YouTube etc. |
| **Ads + weak web gap** | **+10** | Spending on ads without conversion site |
| Phone / WhatsApp | +8 | |
| Email | +4 | |
| Social profiles | +3 | |
| Core niche | +6 | café/jeweller/clothing/shoes/multi-retail |
| City known | +2 | |

Capped at **100**.

### Best lead pattern
Independent jeweller/clothing/café **running Instagram product ads** with **no website** → usually **90–100**.

Fields stored:
- `lead_score` — number
- `score_breakdown` — short one-liner of factors
- `score_factors` — full detail for Sheets

## Google Sheets columns

All of: identity, contacts, independence, **ads** (`runs_ads`, `ad_platforms`, `ad_topics`, `ad_style`, platform flags, evidence), **score** fields, status, packages, timestamps.

## Free Sheets setup

1. New Google Sheet → copy ID  
2. Cloud Console → enable Sheets + Drive APIs  
3. Service account JSON key  
4. Share sheet with service account email (Editor)  
5. Secrets: `GOOGLE_SHEET_ID` + `GOOGLE_SERVICE_ACCOUNT_JSON`  
6. Dashboard → **Google Sheets** → Push  

Auto-sync runs on every lead save when `SHEETS_AUTO_SYNC=true`.
