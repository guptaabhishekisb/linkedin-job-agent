"""
Send an email summary of the latest agent run.
Reads the run log saved by extract_jobs.py and sends a formatted email.
"""

import json
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

RUN_LOG_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'last_run.json')

EMAIL_ENABLED = os.environ.get('EMAIL_ENABLED', 'false').lower() == 'true'
EMAIL_SENDER = os.environ.get('EMAIL_SENDER', '')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')
EMAIL_RECIPIENT = os.environ.get('EMAIL_RECIPIENT', '')
SMTP_HOST = os.environ.get('EMAIL_SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('EMAIL_SMTP_PORT', '587'))
GOOGLE_SHEET_ID = os.environ.get('GOOGLE_SHEET_ID', '')


def build_email_body(log: dict) -> tuple[str, str]:
    """Build subject and HTML body from run log."""
    jobs_found = log.get('pm_jobs_found', 0)
    run_date = log.get('run_date', datetime.now().strftime('%Y-%m-%d'))
    total = log.get('total_posts_analyzed', 0)
    skipped = log.get('duplicates_skipped', 0)

    subject = f"LinkedIn PM Job Agent — {jobs_found} new job(s) found ({run_date})"

    # Build job list
    job_rows = ''
    for j in log.get('job_summaries', []):
        title = j.get('title', 'N/A') or 'N/A'
        company = j.get('company', 'N/A') or 'N/A'
        location = j.get('location', 'N/A') or 'N/A'
        job_rows += f"""
        <tr>
            <td style="padding:8px;border:1px solid #ddd;">{title}</td>
            <td style="padding:8px;border:1px solid #ddd;">{company}</td>
            <td style="padding:8px;border:1px solid #ddd;">{location}</td>
        </tr>"""

    sheet_link = f'https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit' if GOOGLE_SHEET_ID else '#'

    if jobs_found > 0:
        jobs_table = f"""
        <table style="border-collapse:collapse;width:100%;margin:16px 0;">
            <tr style="background:#1F4E79;color:white;">
                <th style="padding:8px;border:1px solid #ddd;text-align:left;">Job Title</th>
                <th style="padding:8px;border:1px solid #ddd;text-align:left;">Company</th>
                <th style="padding:8px;border:1px solid #ddd;text-align:left;">Location</th>
            </tr>
            {job_rows}
        </table>"""
    else:
        jobs_table = '<p style="color:#666;">No new Product Management jobs were found in today\'s feed.</p>'

    body = f"""
    <html>
    <body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
        <h2 style="color:#1F4E79;">LinkedIn PM Job Agent — Daily Report</h2>
        <p><strong>Date:</strong> {run_date}</p>

        <div style="background:#f5f5f5;padding:12px 16px;border-radius:6px;margin:16px 0;">
            <strong>Summary:</strong><br>
            Posts scanned: {total}<br>
            New PM jobs found: <strong>{jobs_found}</strong><br>
            Duplicate posts skipped: {skipped}
        </div>

        {jobs_table}

        <p>
            <a href="{sheet_link}"
               style="display:inline-block;padding:10px 20px;background:#1F4E79;color:white;
                      text-decoration:none;border-radius:4px;">
                Open Google Sheet
            </a>
        </p>

        <hr style="border:none;border-top:1px solid #ddd;margin:24px 0;">
        <p style="color:#999;font-size:12px;">
            Sent by LinkedIn PM Job Agent • Powered by Claude
        </p>
    </body>
    </html>"""

    return subject, body


def send_notification():
    if not EMAIL_ENABLED:
        print("Email notifications are disabled. Set EMAIL_ENABLED=true in .env")
        return

    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT]):
        print("ERROR: Email config incomplete. Check EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT in .env")
        return

    if not os.path.exists(RUN_LOG_FILE):
        print("ERROR: No run log found. Run extract_jobs.py first.")
        return

    with open(RUN_LOG_FILE, 'r') as f:
        log = json.load(f)

    subject, body = build_email_body(log)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECIPIENT
    msg.attach(MIMEText(body, 'html'))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Email sent to {EMAIL_RECIPIENT}")
        print(f"  Subject: {subject}")
    except Exception as e:
        print(f"ERROR: Failed to send email: {e}")


if __name__ == '__main__':
    send_notification()
