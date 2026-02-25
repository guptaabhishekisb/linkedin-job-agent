# CLAUDE.md — Instructions for Claude Code Agent

## Project Purpose
This agent scrapes the user's LinkedIn feed, identifies **Product Management** job postings using the **Claude Code CLI** (`claude -p`), publishes structured results to a Google Sheet, and sends an email summary.

## How to Run

### Full daily pipeline
```bash
python scripts/run_daily.py
```

### Individual stages
```bash
python scripts/scrape_feed.py           # Stage 1: Scrape LinkedIn feed
python scripts/extract_jobs.py          # Stage 2: Extract PM jobs → Google Sheet
python scripts/send_notification.py     # Send email summary of last run
```

## Key Files
- `scripts/scrape_feed.py` — Playwright scraper, scrolls feed, saves posts as JSON
- `scripts/extract_jobs.py` — Claude Code CLI analysis, PM filtering, Google Sheets publish
- `scripts/send_notification.py` — Email notification with run summary
- `scripts/run_daily.py` — Orchestrator running all stages
- `scripts/setup_browser_profile.py` — One-time LinkedIn login
- `data/scraped_posts/` — Raw JSON files named by date (`feed_YYYY-MM-DD.json`)
- `data/last_run.json` — Run log written by `extract_jobs.py`, read by `send_notification.py`
- `output/fallback_jobs_YYYY-MM-DD.json` — Local fallback if Google Sheets write fails
- `credentials/google_service_account.json` — Google API credentials (gitignored)
- `.env` — Config and credentials (gitignored)

## Environment Variables (in .env)
- `ANTHROPIC_API_KEY` — Used by the `claude` CLI for authentication (not read directly by Python scripts)
- `GOOGLE_SHEET_ID` — Spreadsheet ID from the Google Sheets URL
- `GOOGLE_CREDENTIALS_PATH` — Path to service account JSON
- `EMAIL_ENABLED` — true/false
- `EMAIL_SENDER`, `EMAIL_PASSWORD`, `EMAIL_RECIPIENT` — Gmail SMTP config
- `EMAIL_SMTP_HOST`, `EMAIL_SMTP_PORT` — SMTP server (default: Gmail)

## Google Sheet Columns (EXACT ORDER — do not change)
1. **Sr. No.** — Auto-incrementing integer
2. **Date of Post** — Approximate date (calculated from "2d ago" etc.)
3. **Name of the Poster** — Person who posted
4. **Company** — Hiring company
5. **Job Profile** — Category (e.g., "Product Management", "Product Analytics")
6. **Job Title** — Specific role (e.g., "Senior Product Manager")
7. **Experience Level** — Entry / Mid / Senior / Lead / Executive
8. **Location** — Job location
9. **Salary** — If mentioned
10. **Link to the post** — LinkedIn post URL
11. **Link to any embedded link in the post** — External URLs from the post

All fields except Sr. No. are optional. Leave blank (empty string) if not available.

## Product Management Filter
ONLY extract posts related to Product Management. Include posts about:
- Product Manager, Senior PM, Group PM, VP of Product, CPO, Head of Product
- Product Owner, Product Lead, Product Analyst, Product Operations
- Associate Product Manager (APM), Technical Product Manager
- Growth PM, Platform PM, AI/ML PM, Data PM

EXCLUDE posts about:
- Project Management (PMP, Scrum Master, etc.) — unless also a Product role
- Program Management — unless clearly a Product role
- Sales, Marketing, Engineering, Design roles (even if at product companies)
- General career advice, thought leadership, "I got a new job" announcements

## Data Preservation Rules
- **NEVER overwrite or delete existing rows** in the Google Sheet
- Always APPEND new rows after the last existing row
- Sr. No. continues from the last number in the sheet
- Deduplication: skip posts whose "Link to the post" already exists in column J

## Error Handling
- If browser session expired → print message, ask user to re-run setup_browser_profile.py
- If no PM jobs found → log the run, don't modify the sheet, still send email ("0 jobs found")
- If Claude Code CLI fails → fall back to individual post analysis; skip posts that time out
- If Google Sheets API fails → save results to local `output/fallback_jobs_{date}.json` as backup
- If email fails → log the error, don't crash the pipeline

## Dependencies
- Python 3.9+
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code` + `claude` login)
- pip packages: `playwright`, `gspread`, `google-auth`, `python-dotenv`

> Note: `anthropic` SDK is **not** used directly. Analysis is done via the `claude -p` CLI subprocess.
