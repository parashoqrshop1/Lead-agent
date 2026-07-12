# Fix Streamlit Cloud Python 3.14 install failure

Streamlit Community Cloud **ignores** `runtime.txt`.
You must set Python version in the **Streamlit UI**.

## Required steps (phone OK)

1. Open https://share.streamlit.io
2. Open your app `lead-agent-...`
3. Click **⋮** (or app settings / Manage app)
4. Open **Settings**
5. Find **Python version**
6. Select **3.12** (or 3.11 if shown)
7. Save
8. **Reboot** the app

## If Python version setting is missing

1. Delete the current app
2. Click **New app**
3. Repo: `parashoqrshop1/Lead-agent`
4. Branch: `main`
5. Main file: `dashboard/app.py`
6. Open **Advanced settings**
7. Python version: **3.12**
8. Secrets:

```toml
SCRAPER_MODE = "demo"
DASHBOARD_PASSWORD = "demo123"
AGENCY_NAME = "Your Web Agency"
```

9. Deploy

## Success looks like

```text
Using Python 3.12.x environment
You can now view your Streamlit app
```

If logs still say `Using Python 3.14.6`, the UI Python version was not applied.
