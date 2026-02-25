# LinkedIn Feed Job Extractor Agent — Product Management

An automated agent built with **Claude Code** that scrapes your LinkedIn feed for **Product Management** job postings and publishes them to a Google Sheet, with daily email notifications.

---

## Architecture Overview

```
┌──────────────────────┐
│  Stage 1: Scraper    │
│  (Playwright)        │
│                      │
│  - Opens LinkedIn    │
│  - Scrolls feed      │
│  - Extracts posts    │
│  - Saves to JSON     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Stage 2: Extractor  │
│  (Claude API)        │
│                      │
│  - Filters for PM    │
│    roles only        │
│  - Extracts fields   │
│  - Deduplicates      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐     ┌──────────────────┐
│  Google Sheets       │     │  Email Summary   │
│  (gspread)           │     │  (smtplib)       │
│                      │     │                  │
│  Appends new rows,   │     │  "5 new PM jobs  │
│  preserves old data  │     │   found today"   │
└──────────────────────┘     └──────────────────┘
```

---

## Google Sheet Columns

| # | Column | Notes |
|---|--------|-------|
| 1 | Sr. No. | Auto-incrementing serial number |
| 2 | Date of Post | Approximate date from LinkedIn |
| 3 | Name of the Poster | Who posted/shared the job |
| 4 | Company | Hiring company |
| 5 | Job Profile | e.g., Product Management, Product Analytics |
| 6 | Job Title | The specific role title |
| 7 | Experience Level | Entry / Mid / Senior / Lead / Executive |
| 8 | Location | Job location |
| 9 | Salary | If mentioned in the post |
| 10 | Link to the post | LinkedIn post URL |
| 11 | Link to any embedded link in the post | External URLs found in the post |

All fields except Sr. No. are optional — left blank if not available.

---

## Prerequisites

### 1. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Google Sheets API Setup
You need a Google Cloud service account to write to your sheet:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable the **Google Sheets API** and **Google Drive API**
4. Go to **Credentials** → **Create Credentials** → **Service Account**
5. Download the JSON key file
6. Save it as `credentials/google_service_account.json` in this project
7. Open your Google Sheet and **share it** with the service account email
   (the email looks like `something@project-id.iam.gserviceaccount.com`)
   — give it **Editor** access

Your target Google Sheet:
```
https://docs.google.com/spreadsheets/d/e/2PACX-1vQD5xWhWAQ0AQnsENumla96ia68b8JjfgekGvsHhUUs8bVe_CcwIwCQaQyRjRp6m01S8d9YR1p6jWEG/pub?output=xlsx
```

> **Note**: The published URL above is a read-only export link. You'll need the
> **editable** spreadsheet URL to extract the Spreadsheet ID. Open the sheet in
> Google Sheets normally — the URL will look like:
> `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`
> Copy that SPREADSHEET_ID and set it in your `.env` file (see below).

### 3. LinkedIn Browser Profile
```bash
python scripts/setup_browser_profile.py
```
Log in manually, then close the browser. Your password is never stored.

### 4. Environment Variables
Create a `.env` file in the project root:
```bash
# Required
ANTHROPIC_API_KEY=your-anthropic-api-key

# Google Sheets
GOOGLE_SHEET_ID=your-spreadsheet-id-from-url
GOOGLE_CREDENTIALS_PATH=credentials/google_service_account.json

# Email notifications (optional — uses Gmail SMTP by default)
EMAIL_ENABLED=true
EMAIL_SENDER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_RECIPIENT=your-email@gmail.com
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
```

> **Gmail App Password**: Go to Google Account → Security → 2-Step Verification
> → App Passwords → Generate one for "Mail". Use that, not your regular password.

---

## Usage

### Run Manually
```bash
# Full pipeline (scrape → extract → publish → email)
python scripts/run_daily.py

# Individual stages
python scripts/scrape_feed.py          # Stage 1 only
python scripts/extract_jobs.py         # Stage 2 only
python scripts/send_notification.py    # Email only (sends last run summary)
```

### Run with Claude Code
```bash
cd linkedin-job-agent
claude
```
Then ask:
- "Run the daily job scrape"
- "Show me today's results"
- "Change the PM keyword filters"
- "Increase the scroll count to capture more posts"

### Schedule via Cron (Daily at 8 AM)
```bash
crontab -e
# Add:
0 8 * * * cd /path/to/linkedin-job-agent && /usr/bin/python scripts/run_daily.py >> logs/daily.log 2>&1
```

---

## Project Structure

```
linkedin-job-agent/
├── README.md
├── CLAUDE.md                          # Claude Code instructions
├── requirements.txt
├── .env                               # Your API keys (gitignored)
├── .gitignore
├── credentials/
│   └── google_service_account.json    # Google API key (gitignored)
├── scripts/
│   ├── setup_browser_profile.py       # One-time LinkedIn login
│   ├── scrape_feed.py                 # Stage 1: Scrape feed
│   ├── extract_jobs.py                # Stage 2: Extract + publish to Sheets
│   ├── send_notification.py           # Email notification
│   └── run_daily.py                   # Orchestrator
├── data/
│   ├── browser_profile/               # Browser cookies (gitignored)
│   └── scraped_posts/                 # Raw JSON data
└── logs/
```

---

## Customization

### Adjust PM Keywords
Edit the `PM_KEYWORDS` list in `scripts/extract_jobs.py` to broaden or narrow the filter.

### Change Scroll Depth
In `scripts/scrape_feed.py`:
```python
SCROLL_COUNT = 25  # Increase for more posts
```

### Re-login (Session Expired)
```bash
python scripts/setup_browser_profile.py
```

---

## Important Notes

- **Privacy**: Your LinkedIn password and Google credentials are never committed to git.
- **Append-only**: The agent only appends new rows. Existing data is never overwritten or deleted.
- **Deduplication**: Posts with the same LinkedIn URL are skipped on subsequent runs.
- **PM Focus**: Only posts related to Product Management roles are captured.
- **LinkedIn ToS**: Automated access may violate LinkedIn's Terms. Use responsibly for personal use.
