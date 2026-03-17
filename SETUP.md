# Deal Desk Daily Report — Setup Guide

## 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Google Service Account (Sheets + Drive access)

### 2a. Create the service account
1. Go to https://console.cloud.google.com
2. Create a new project (or use an existing one)
3. Enable these two APIs:
   - **Google Sheets API**
   - **Google Drive API**
4. Go to **IAM & Admin → Service Accounts → Create Service Account**
5. Name it (e.g. `deal-desk-report`) and click Create
6. On the service account page → **Keys → Add Key → JSON** → download the file
7. Save it to `config/service_account.json` in this repo

### 2b. Share the Google Sheet with the service account
1. Open the service account JSON — copy the `client_email` value
   (looks like `deal-desk-report@your-project.iam.gserviceaccount.com`)
2. Open the Google Sheet → Share → paste that email → set to **Viewer**

### 2c. Share the target Drive folder (for report upload)
1. Create a folder in Google Drive where reports should land
2. Share it with the same service account email → set to **Editor**
3. Open the folder → copy the folder ID from the URL
   (`https://drive.google.com/drive/folders/FOLDER_ID_HERE`)
4. Add it to `.env` as `GOOGLE_DRIVE_FOLDER_ID`

## 3. Chorus access token

Chorus uses OAuth/SSO. Until you have a proper OAuth app set up, the quickest
path for scheduled use:

1. Log into Chorus in your browser
2. Open DevTools (F12) → Network tab
3. Refresh the page and find any XHR request to `api.chorus.ai`
4. Copy the `Authorization` header value (e.g. `Bearer eyJ...`)
5. Paste the token into `.env` as `CHORUS_ACCESS_TOKEN`

> **Note:** Tokens typically expire after 24h–7 days. You'll need to refresh
> this periodically. A proper OAuth app setup with your Chorus admin can provide
> longer-lived tokens.

## 4. Anthropic API key

1. Go to https://console.anthropic.com → API Keys → Create key
2. Add to `.env` as `ANTHROPIC_API_KEY`

## 5. Configure .env

```bash
cp .env.example .env
# then edit .env with your values
```

## 6. Discover column names from the sheet

Before the first real run, print the sheet's column names:

```bash
python main.py --columns
```

Share the output here so the column mappings in the code can be confirmed/updated.

## 7. Run a one-shot test

```bash
python main.py
```

## 8. Start the daily scheduler

```bash
python scheduler.py
```

The scheduler fires at `REPORT_TIME` (default 17:00) in `TIMEZONE` (default America/New_York).
Run it inside `screen`, `tmux`, or as a systemd service to keep it alive.

### Optional: systemd service

```ini
# /etc/systemd/system/deal-desk-report.service
[Unit]
Description=Deal Desk Daily Report Scheduler
After=network.target

[Service]
WorkingDirectory=/path/to/Claude-Experiments
ExecStart=/path/to/.venv/bin/python scheduler.py
Restart=always
EnvironmentFile=/path/to/Claude-Experiments/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable deal-desk-report
sudo systemctl start deal-desk-report
```
