"""
One-time setup: Opens a browser window for you to log into LinkedIn.
Your session cookies are saved locally so the scraper can reuse them.
Your password is NEVER stored or seen by any script.
"""

import os
from playwright.sync_api import sync_playwright

PROFILE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'browser_profile')


def main():
    os.makedirs(PROFILE_DIR, exist_ok=True)
    profile_path = os.path.abspath(PROFILE_DIR)

    print("=" * 60)
    print("LinkedIn Browser Profile Setup")
    print("=" * 60)
    print()
    print("A browser window will open. Please:")
    print("  1. Go to https://www.linkedin.com")
    print("  2. Log in with your credentials")
    print("  3. Complete any 2FA/verification if prompted")
    print("  4. Wait until you can see your feed")
    print("  5. Close the browser window")
    print()
    print(f"Session will be saved to: {profile_path}")
    print()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            profile_path,
            headless=False,
            viewport={'width': 1280, 'height': 900},
            args=['--disable-blink-features=AutomationControlled'],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto('https://www.linkedin.com/login')

        print("Waiting for you to log in and close the browser...")
        try:
            page.wait_for_event('close', timeout=300000)
        except Exception:
            pass

        context.close()

    print()
    print("Session saved! You can now run the scraper.")
    print("If your session expires later, re-run this script.")


if __name__ == '__main__':
    main()
