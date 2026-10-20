import os
import sys
import time
import shutil
import threading
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_BOT_TOKEN = "123456789:TEST_BOT_TOKEN_SECRET"
os.environ["BOT_TOKEN"] = TEST_BOT_TOKEN

from api.config import settings
settings.BOT_TOKEN = TEST_BOT_TOKEN

import uvicorn
from playwright.sync_api import sync_playwright
from api.main import app
from tests.conftest import generate_test_init_data

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "screenshots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PORT = 8094
BASE_URL = f"http://127.0.0.1:{PORT}"


def run_server():
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


def main():
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server
    import urllib.request
    for _ in range(20):
        try:
            with urllib.request.urlopen(f"{BASE_URL}/api/health", timeout=1) as response:
                if response.status == 200:
                    break
        except Exception:
            time.sleep(0.5)

    admin_init_data = generate_test_init_data(
        user_id=12345678,
        first_name="Sakura Owner",
        username="fkhrdnvvvva",
        secret_token=TEST_BOT_TOKEN,
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 412, "height": 892},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Telegram-iOS/10.0",
            device_scale_factor=2,
        )
        page = context.new_page()

        page.add_init_script(f"""
            window.Telegram = {{
                WebApp: {{
                    initData: "{admin_init_data}",
                    initDataUnsafe: {{
                        user: {{
                            id: 12345678,
                            first_name: "Sakura",
                            last_name: "Owner",
                            username: "fkhrdnvvvva",
                            language_code: "uz"
                        }}
                    }},
                    ready: () => {{}},
                    expand: () => {{}},
                    setHeaderColor: () => {{}},
                    setBackgroundColor: () => {{}},
                    HapticFeedback: {{
                        impactOccurred: () => {{}},
                        notificationOccurred: () => {{}},
                        selectionChanged: () => {{}}
                    }},
                    BackButton: {{
                        show: () => {{}},
                        hide: () => {{}},
                        onClick: () => {{}},
                        offClick: () => {{}}
                    }},
                    MainButton: {{
                        setText: () => {{}},
                        show: () => {{}},
                        hide: () => {{}},
                        enable: () => {{}},
                        disable: () => {{}},
                        showProgress: () => {{}},
                        hideProgress: () => {{}},
                        onClick: () => {{}},
                        offClick: () => {{}}
                    }},
                    openTelegramLink: (url) => {{ window.open(url, '_blank'); }},
                    openLink: (url) => {{ window.open(url, '_blank'); }}
                }}
            }};
        """)

        # Go to product detail page and click "Savatga qo'shish"
        page.goto(f"{BASE_URL}/?product=1", wait_until="networkidle")
        page.wait_for_timeout(1000)

        # Click add to bag button
        add_btn = page.locator("button:has-text('Savatga qo\\'shish')")
        if add_btn.count() > 0:
            add_btn.first.click()
            page.wait_for_timeout(1500)

        # Click Orqaga button to return to main tabs
        back_btn = page.locator("button:has-text('Orqaga')")
        if back_btn.count() > 0:
            back_btn.first.click()
            page.wait_for_timeout(800)

        # Click the Bag tab at the bottom
        bag_nav = page.locator("button:has-text('Savat')")
        if bag_nav.count() > 0:
            bag_nav.first.click()
            page.wait_for_timeout(1000)

        bag_path = OUTPUT_DIR / "03_bag_screen.png"
        page.screenshot(path=str(bag_path))
        print(f"Captured full bag: {bag_path}")

        brain_dir = Path("C:/Users/User/.gemini/antigravity/brain/bc829266-abe1-4184-a16f-93e386940573")
        shutil.copy(str(bag_path), str(brain_dir / "03_bag_screen.png"))

        browser.close()

    print("Done!")


if __name__ == "__main__":
    main()
