"""
Daily orchestrator: Runs scrape → extract → email notification in sequence.
Designed to be called by cron or manually.
"""

import sys
from datetime import datetime

from scrape_feed import scrape_feed
from extract_jobs import extract_jobs
from send_notification import send_notification


def main():
    print("=" * 60)
    print(f"LinkedIn PM Job Agent — Daily Run")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Stage 1: Scrape
    print("\n--- Stage 1: Scraping LinkedIn Feed ---\n")
    result = scrape_feed()
    if result is None:
        print("\nScraping failed. Aborting.")
        sys.exit(1)

    # Stage 2: Extract & publish to Google Sheet
    print("\n--- Stage 2: Extracting PM Job Postings ---\n")
    jobs_found = extract_jobs()

    # Stage 3: Email notification
    print("\n--- Stage 3: Sending Email Notification ---\n")
    try:
        send_notification()
    except Exception as e:
        print(f"Email notification failed (non-fatal): {e}")

    print("\n" + "=" * 60)
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"PM jobs found: {jobs_found or 0}")
    print("=" * 60)


if __name__ == '__main__':
    main()
