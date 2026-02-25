"""
Stage 1: Scrape LinkedIn feed using Playwright.
Scrolls through the feed, extracts post content, and saves to JSON.
Uses an existing browser profile (created via setup_browser_profile.py).
"""

import json
import os
import random
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

PROFILE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'browser_profile')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'scraped_posts')

SCROLL_COUNT = 25
SCROLL_DELAY_MIN = 3
SCROLL_DELAY_MAX = 7
SCROLL_PIXELS = 800


def scrape_feed():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    profile_path = os.path.abspath(PROFILE_DIR)

    if not os.path.exists(profile_path):
        print("ERROR: Browser profile not found.")
        print("Please run setup_browser_profile.py first to log into LinkedIn.")
        return None

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting LinkedIn feed scrape...")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            profile_path,
            headless=True,
            viewport={'width': 1280, 'height': 900},
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-gpu',
            ],
        )
        page = context.pages[0] if context.pages else context.new_page()

        # Use 'domcontentloaded' — LinkedIn never reaches 'networkidle'
        # due to constant background requests (notifications, ads, etc.)
        try:
            page.goto('https://www.linkedin.com/feed/', wait_until='domcontentloaded', timeout=60000)
        except Exception as e:
            print(f"ERROR: Could not load LinkedIn feed: {e}")
            print("Possible causes:")
            print("  - No internet connection")
            print("  - LinkedIn session expired (re-run setup_browser_profile.py)")
            print("  - LinkedIn is blocking automated access")
            context.close()
            return None

        # Give the page extra time to render dynamic content
        time.sleep(5)

        if '/login' in page.url or '/authwall' in page.url:
            print("ERROR: LinkedIn session has expired.")
            print("Please re-run setup_browser_profile.py to log in again.")
            context.close()
            return None

        print(f"  Current URL: {page.url}")

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Feed loaded. Starting scroll...")

        for i in range(SCROLL_COUNT):
            page.evaluate(f'window.scrollBy(0, {SCROLL_PIXELS})')
            delay = random.uniform(SCROLL_DELAY_MIN, SCROLL_DELAY_MAX)
            print(f"  Scroll {i + 1}/{SCROLL_COUNT} — waiting {delay:.1f}s")
            time.sleep(delay)

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Scrolling complete. Extracting posts...")

        posts = page.evaluate('''() => {
            const postElements = document.querySelectorAll('.feed-shared-update-v2');
            const posts = [];

            for (const el of postElements) {
                try {
                    const actorEl = el.querySelector('.update-components-actor__name .visually-hidden') ||
                                    el.querySelector('.update-components-actor__name');
                    const posterName = actorEl ? actorEl.innerText.trim() : '';

                    const titleEl = el.querySelector('.update-components-actor__description .visually-hidden') ||
                                    el.querySelector('.update-components-actor__description');
                    const posterTitle = titleEl ? titleEl.innerText.trim() : '';

                    const timeEl = el.querySelector('.update-components-actor__sub-description .visually-hidden') ||
                                   el.querySelector('time') ||
                                   el.querySelector('.update-components-actor__sub-description');
                    const postTime = timeEl ? timeEl.innerText.trim() : '';

                    const textEl = el.querySelector('.feed-shared-update-v2__description') ||
                                   el.querySelector('.update-components-text');
                    const postText = textEl ? textEl.innerText.trim() : '';

                    const urnAttr = el.getAttribute('data-urn') || '';
                    let postLink = '';
                    if (urnAttr) {
                        const activityId = urnAttr.split(':').pop();
                        postLink = `https://www.linkedin.com/feed/update/urn:li:activity:${activityId}/`;
                    }

                    const links = [];
                    const linkEls = el.querySelectorAll('a[href]');
                    for (const a of linkEls) {
                        const href = a.href;
                        if (href && !href.includes('linkedin.com/feed') &&
                            !href.includes('#') && !href.includes('linkedin.com/in/')) {
                            links.push(href);
                        }
                    }

                    if (postText.length > 10) {
                        posts.push({
                            poster_name: posterName,
                            poster_title: posterTitle,
                            post_time: postTime,
                            post_text: postText,
                            post_link: postLink,
                            embedded_links: [...new Set(links)].slice(0, 5),
                        });
                    }
                } catch (e) {}
            }
            return posts;
        }''')

        context.close()

    today = datetime.now().strftime('%Y-%m-%d')
    output_file = os.path.join(OUTPUT_DIR, f'feed_{today}.json')

    output_data = {
        'scrape_date': today,
        'scrape_timestamp': datetime.now().isoformat(),
        'post_count': len(posts),
        'posts': posts,
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Saved {len(posts)} posts to {output_file}")
    return output_file


if __name__ == '__main__':
    scrape_feed()
