"""
Stage 2: Extract Product Management job postings from scraped LinkedIn feed.
Uses Claude Code CLI (claude -p) for analysis — requires Claude Code installed and logged in.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

SCRAPED_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'scraped_posts')
FALLBACK_DIR = os.path.join(os.path.dirname(__file__), '..', 'output')
RUN_LOG_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'last_run.json')

GOOGLE_SHEET_ID = os.environ.get('GOOGLE_SHEET_ID', '')
GOOGLE_CREDENTIALS_PATH = os.environ.get(
    'GOOGLE_CREDENTIALS_PATH',
    os.path.join(os.path.dirname(__file__), '..', 'credentials', 'google_service_account.json'),
)

SHEET_HEADERS = [
    'Sr. No.', 'Date of Post', 'Name of the Poster', 'Company',
    'Job Profile', 'Job Title', 'Experience Level', 'Location',
    'Salary', 'Link to the post', 'Link to any embedded link in the post',
]

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]

# ── Prompt for Claude Code CLI ───────────────────────────────────────────────

ANALYSIS_PROMPT = """I have a LinkedIn post and I need your help determining if it's about a Product Management job opening. Please analyze it and give me the details in JSON format.

Here's the post:

Poster: {poster_name}
Poster Headline: {poster_title}
Time posted: {post_time}
Post content:
{post_text}

Links found in post: {links}

Please classify this as a PM job if it mentions hiring for roles like Product Manager, Senior PM, Group PM, VP Product, CPO, Head of Product, Product Owner, Product Lead, Product Analyst, APM, Technical PM, Growth PM, Platform PM, AI/ML PM, or Data PM.

It's NOT a PM job if it's about Project Management, Program Management, Scrum Master, Engineering, Design, Sales, Marketing roles, career advice, thought leadership, or someone announcing their own new job.

Please respond with only a JSON object in this format:
{{"is_pm_job": false, "confidence": 0.5, "date_of_post": "", "company": "", "job_profile": "", "job_title": "", "experience_level": "", "location": "", "salary": ""}}

Use empty strings for any fields you can't determine."""


def check_claude_code_installed() -> bool:
    """Verify Claude Code CLI is available."""
    return shutil.which('claude') is not None


def get_latest_scrape():
    if not os.path.exists(SCRAPED_DIR):
        return None
    files = sorted(
        [f for f in os.listdir(SCRAPED_DIR) if f.endswith('.json')],
        reverse=True,
    )
    return os.path.join(SCRAPED_DIR, files[0]) if files else None


def parse_relative_time(time_str: str) -> str:
    today = datetime.now()
    time_str = time_str.lower().strip()
    if not time_str:
        return ''
    if 'just now' in time_str or 'moment' in time_str:
        return today.strftime('%Y-%m-%d')
    for unit, delta in [('w', 7), ('d', 1), ('h', 1 / 24), ('m', 1 / 1440)]:
        if unit in time_str:
            try:
                num = int(''.join(c for c in time_str.split(unit)[0] if c.isdigit()) or '1')
                return (today - timedelta(days=num * delta)).strftime('%Y-%m-%d')
            except ValueError:
                pass
    return ''


def call_claude_code(prompt: str, timeout: int = 60) -> str | None:
    """Call Claude Code CLI from /tmp to avoid project CLAUDE.md interfering."""
    try:
        # Small delay to avoid rate limiting
        time.sleep(3)

        result = subprocess.run(
            ['claude', '-p', '--output-format', 'text', '--max-turns', '1'],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd='/tmp',
        )

        text = result.stdout.strip()
        if not text:
            print(f"  Warning: No output. stderr: {result.stderr[:200]}")
            return None

        # Strip markdown code fences if present (```json ... ```)
        if '```' in text:
            lines = text.split('\n')
            cleaned = []
            for line in lines:
                if line.strip().startswith('```'):
                    continue
                cleaned.append(line)
            text = '\n'.join(cleaned).strip()

        return text

    except subprocess.TimeoutExpired:
        print("  Warning: Claude Code timed out.")
        return None
    except Exception as e:
        print(f"  Warning: Error calling Claude Code: {e}")
        return None


def analyze_post(post: dict) -> dict | None:
    """Use Claude Code CLI (claude -p) to analyze a single post."""
    prompt = ANALYSIS_PROMPT.format(
        poster_name=post.get('poster_name', ''),
        poster_title=post.get('poster_title', ''),
        post_time=post.get('post_time', ''),
        post_text=post.get('post_text', '')[:2000],
        links=', '.join(post.get('embedded_links', [])),
    )

    text = call_claude_code(prompt, timeout=60)
    if not text:
        print(f"  Debug: call_claude_code returned None/empty for {post.get('poster_name', '?')[:20]}")
        return None

    try:
        # Extract JSON from response
        json_start = text.find('{')
        json_end = text.rfind('}')
        if json_start != -1 and json_end != -1:
            json_text = text[json_start:json_end + 1]
        else:
            print(f"  Debug: No JSON braces found. Response was: {text[:200]}")
            return None

        return json.loads(json_text)

    except json.JSONDecodeError as e:
        print(f"  Warning: Could not parse response for post by {post.get('poster_name', '?')}: {e}")
        print(f"  Debug: Raw text was: {text[:200]}")
        return None


# ── Batch analysis (more efficient) ─────────────────────────────────────────

def analyze_posts_batch(posts: list, existing_links: set) -> list:
    """Analyze all posts in a single Claude Code call for efficiency."""

    # Filter out duplicates first
    new_posts = []
    for post in posts:
        post_link = post.get('post_link', '')
        if not post_link or post_link not in existing_links:
            new_posts.append(post)

    if not new_posts:
        return []

    # Build a batch prompt with all posts
    posts_text = ""
    for i, post in enumerate(new_posts):
        posts_text += f"""
--- POST {i + 1} ---
Poster: {post.get('poster_name', '')}
Headline: {post.get('poster_title', '')}
Time: {post.get('post_time', '')}
Content: {post.get('post_text', '')[:1000]}
Links: {', '.join(post.get('embedded_links', []))}
"""

    batch_prompt = f"""I have {len(new_posts)} LinkedIn posts and I need help identifying which ones are Product Management job openings. Please analyze each one.

PM roles to look for: Product Manager, Senior PM, Group PM, VP Product, CPO, Head of Product, Product Owner, Product Lead, Product Analyst, APM, Technical PM, Growth PM, Platform PM, AI/ML PM, Data PM.

Not PM jobs: Project Management, Program Management, Scrum Master, Engineering, Design, Sales, Marketing roles, career advice, thought leadership, "I got a new job" posts.

Here are the posts:

{posts_text}

Please respond with a JSON array containing one object per post, in order. Format:
[{{"post_index": 1, "is_pm_job": false, "confidence": 0.1, "date_of_post": "", "company": "", "job_profile": "", "job_title": "", "experience_level": "", "location": "", "salary": ""}}]

Use empty strings for unknown fields. Include all {len(new_posts)} posts."""

    print(f"  Sending {len(new_posts)} posts to Claude Code for batch analysis...")

    text = call_claude_code(batch_prompt, timeout=180)

    if not text:
        print("  Debug: Batch call_claude_code returned None/empty.")
        print("  Falling back to individual analysis.")
        return analyze_posts_individually(new_posts)

    try:
        # Extract JSON array from response
        json_start = text.find('[')
        json_end = text.rfind(']')
        if json_start != -1 and json_end != -1:
            text = text[json_start:json_end + 1]
        else:
            print(f"  Warning: No JSON array in batch response. Falling back.")
            print(f"  Debug: Batch response was: {text[:300]}")
            return analyze_posts_individually(new_posts)

        results = json.loads(text)
        print(f"  Batch analysis complete. Got {len(results)} results.")

        # Pair results back with posts
        paired = []
        for r in results:
            idx = r.get('post_index', 0) - 1
            if 0 <= idx < len(new_posts):
                paired.append((new_posts[idx], r))

        return paired

    except json.JSONDecodeError as e:
        print(f"  Warning: Could not parse batch response: {e}")
        print("  Falling back to individual analysis.")
        return analyze_posts_individually(new_posts)


def analyze_posts_individually(posts: list) -> list:
    """Fallback: analyze posts one by one."""
    paired = []
    for i, post in enumerate(posts):
        print(f"  Analyzing post {i + 1}/{len(posts)}: {post.get('poster_name', '?')[:30]}...")
        result = analyze_post(post)
        if result:
            paired.append((post, result))
    return paired


# ── Google Sheets helpers ────────────────────────────────────────────────────

def connect_to_sheet():
    if not GOOGLE_SHEET_ID:
        print("  Note: GOOGLE_SHEET_ID not set. Will save to local fallback file.")
        return None
    if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
        print(f"  Note: Google credentials not found at {GOOGLE_CREDENTIALS_PATH}")
        print("  Will save to local fallback file.")
        return None

    try:
        import gspread
        from google.oauth2.service_account import Credentials
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH, scopes=SCOPES)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        return sh.sheet1
    except ImportError:
        print("  Note: gspread not installed. Will save to local fallback file.")
        return None


def ensure_headers(worksheet):
    existing = worksheet.row_values(1)
    if not existing or existing[0] != SHEET_HEADERS[0]:
        worksheet.update('A1', [SHEET_HEADERS])
        print("  Headers written to Google Sheet.")


def get_existing_post_links(worksheet) -> set:
    try:
        col_values = worksheet.col_values(10)
        return set(col_values[1:])
    except Exception:
        return set()


def get_next_sr_no(worksheet) -> int:
    try:
        col_values = worksheet.col_values(1)
        if len(col_values) <= 1:
            return 1
        last_val = col_values[-1]
        return int(last_val) + 1 if last_val.isdigit() else len(col_values)
    except Exception:
        return 1


def append_rows_to_sheet(worksheet, rows: list):
    if not rows:
        return
    worksheet.append_rows(rows, value_input_option='USER_ENTERED')


# ── Fallback: save to local JSON ────────────────────────────────────────────

def save_fallback(jobs: list):
    os.makedirs(FALLBACK_DIR, exist_ok=True)
    today = datetime.now().strftime('%Y-%m-%d')
    path = os.path.join(FALLBACK_DIR, f'fallback_jobs_{today}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)
    print(f"  Fallback saved to {path}")


# ── Save run log (for email notification) ────────────────────────────────────

def save_run_log(total_posts: int, jobs_found: int, skipped: int, jobs: list):
    log = {
        'run_timestamp': datetime.now().isoformat(),
        'run_date': datetime.now().strftime('%Y-%m-%d'),
        'total_posts_analyzed': total_posts,
        'pm_jobs_found': jobs_found,
        'duplicates_skipped': skipped,
        'job_summaries': [
            {
                'title': j.get('job_title', ''),
                'company': j.get('company', ''),
                'location': j.get('location', ''),
            }
            for j in jobs
        ],
    }
    os.makedirs(os.path.dirname(RUN_LOG_FILE), exist_ok=True)
    with open(RUN_LOG_FILE, 'w') as f:
        json.dump(log, f, indent=2)


# ── Main pipeline ────────────────────────────────────────────────────────────

def extract_jobs():
    # Check Claude Code is installed
    if not check_claude_code_installed():
        print("ERROR: Claude Code CLI not found.")
        print("Install it: npm install -g @anthropic-ai/claude-code")
        print("Then log in: claude (follow the prompts)")
        return

    scrape_file = get_latest_scrape()
    if not scrape_file:
        print("ERROR: No scraped feed data found. Run scrape_feed.py first.")
        return

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Loading scraped data: {scrape_file}")
    with open(scrape_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    posts = data.get('posts', [])
    print(f"  Found {len(posts)} posts to analyze for PM roles")
    print(f"  Using Claude Code CLI (Pro subscription) for analysis")

    # Connect to Google Sheet
    worksheet = None
    existing_links = set()
    next_sr = 1
    try:
        worksheet = connect_to_sheet()
        if worksheet:
            ensure_headers(worksheet)
            existing_links = get_existing_post_links(worksheet)
            next_sr = get_next_sr_no(worksheet)
            print(f"  Google Sheet connected. {len(existing_links)} existing entries. Next Sr. No. = {next_sr}")
    except Exception as e:
        print(f"  Warning: Could not connect to Google Sheets: {e}")
        print("  Will save results to local fallback file.")

    # Pre-flight check: make sure Claude Code has credits
    print("  Running pre-flight check on Claude Code...")
    test_response = call_claude_code('Reply with: {"status": "ok"}', timeout=30)
    if test_response and 'credit' in test_response.lower():
        print(f"  ERROR: Claude Code credits are too low. Response: {test_response}")
        print("  Please wait for credits to reset or upgrade your plan.")
        return
    elif test_response:
        print(f"  Pre-flight OK: Claude Code is responding.")
    else:
        print("  WARNING: Claude Code did not respond. Proceeding anyway...")

    # Analyze posts using Claude Code (one by one with delays to avoid rate limits)
    skipped = 0
    new_posts = []
    for post in posts:
        post_link = post.get('post_link', '')
        if post_link and post_link in existing_links:
            skipped += 1
        else:
            new_posts.append(post)

    print(f"  {skipped} duplicates skipped. Analyzing {len(new_posts)} new posts...")
    paired_results = analyze_posts_individually(new_posts)

    new_rows = []
    extracted_jobs = []

    for post, result in paired_results:
        if result and result.get('is_pm_job') and result.get('confidence', 0) >= 0.6:
            date_of_post = result.get('date_of_post', '') or parse_relative_time(post.get('post_time', ''))
            embedded = ', '.join(post.get('embedded_links', []))

            row = [
                next_sr,
                date_of_post,
                post.get('poster_name', ''),
                result.get('company', ''),
                result.get('job_profile', ''),
                result.get('job_title', ''),
                result.get('experience_level', ''),
                result.get('location', ''),
                result.get('salary', ''),
                post.get('post_link', ''),
                embedded,
            ]
            new_rows.append(row)
            extracted_jobs.append(result)
            next_sr += 1

    # Publish to Google Sheet or fallback
    if new_rows:
        if worksheet:
            try:
                append_rows_to_sheet(worksheet, new_rows)
                print(f"  Appended {len(new_rows)} rows to Google Sheet.")
            except Exception as e:
                print(f"  Error writing to Google Sheets: {e}")
                save_fallback(extracted_jobs)
        else:
            save_fallback(extracted_jobs)
    else:
        print("  No PM job posts found in this batch.")

    # Save run log for email notification
    save_run_log(len(posts), len(new_rows), skipped, extracted_jobs)

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Done!")
    print(f"  PM jobs found: {len(new_rows)}")
    print(f"  Duplicates skipped: {skipped}")
    print(f"  Non-PM posts skipped: {len(posts) - len(new_rows) - skipped}")

    return len(new_rows)


if __name__ == '__main__':
    extract_jobs()
