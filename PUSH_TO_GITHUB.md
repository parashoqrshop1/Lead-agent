# Push this code to https://github.com/parashoqrshop1/Lead-agent

The advanced agent is **committed locally** but this environment has **no GitHub login**, so `git push` failed. Use one method below (phone OK).

---

## Method A — Upload ZIP on phone (easiest)

1. Download **`Lead-agent-upload.zip`** from this workspace  
2. Unzip on your phone (Files app / RAR)  
3. Open https://github.com/parashoqrshop1/Lead-agent  
4. Tap **Add file → Upload files**  
5. Upload **all files and folders** inside the unzipped `Lead-agent` folder  
   (agents, config, dashboard, scripts, README.md, requirements.txt, etc.)  
6. Commit message: `Advanced free multi-agent independent shop lead system`  
7. Commit to **main**

---

## Method B — GitHub web “Upload” from computer

Same as Method A with drag-and-drop of the project folder contents.

---

## Method C — Git from Codespaces / laptop

```bash
git clone https://github.com/parashoqrshop1/Lead-agent.git
cd Lead-agent
# copy project files over the clone (keep .git)
# then:
git add -A
git commit -m "Advanced free multi-agent independent shop lead system"
git push origin main
```

If the empty repo only has LICENSE, overwriting with our files is fine.

---

## Method D — Give a Personal Access Token (PAT) here

1. Phone: GitHub → Settings → Developer settings → Personal access tokens  
2. Generate classic token with `repo` scope  
3. Paste token in chat (or set remote):

```bash
cd Lead-agent
git push https://<TOKEN>@github.com/parashoqrshop1/Lead-agent.git main
```

**Revoke the token after push.** Do not commit the token.

---

## After code is on GitHub

Follow **PHONE_SETUP.md**:

1. Streamlit Cloud → New app → `parashoqrshop1/Lead-agent` → `dashboard/app.py`  
2. Secrets: free Gemini key + `SCRAPER_MODE=open_source` (or `demo`)  
3. Deploy → run Full Pipeline
