import os
import sys
import time
import json
import threading
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from playwright.sync_api import sync_playwright
from api.main import app
from tests.conftest import generate_test_init_data, TEST_BOT_TOKEN
from db.models import Admin, Setting
from db.session import async_session_factory
import asyncio

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "screenshots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PORT = 8088
BASE_URL = f"http://127.0.0.1:{PORT}"


def run_server():
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


def main():
    # 1. Ensure admin user exists in DB for admin screenshot
    async def prepare_admin():
        async with async_session_factory() as session:
            admin_id = 12345678
            from sqlalchemy import select
            res = await session.execute(select(Admin).where(Admin.telegram_id == admin_id))
            if not res.scalars().first():
                session.add(Admin(telegram_id=admin_id, name="Sakura Owner", role="owner"))
                await session.commit()
    asyncio.run(prepare_admin())

    # 2. Start Uvicorn in background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to become responsive
    import urllib.request
    max_wait = 20
    ready = False
    for _ in range(max_wait):
        try:
            with urllib.request.urlopen(f"{BASE_URL}/api/health", timeout=1) as response:
                if response.status == 200:
                    ready = True
                    break
        except Exception:
            time.sleep(0.5)

    if not ready:
        print("Server failed to start in time")
        sys.exit(1)

    print("Server is up and running. Generating screenshots with Playwright...")

    # Generate valid admin initData for tests
    admin_init_data = generate_test_init_data(
        user_id=12345678,
        first_name="Sakura Owner",
        username="fkhrdnvvvva",
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Mobile Telegram viewport
        context = browser.new_context(
            viewport={"width": 412, "height": 892},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Telegram-iOS/10.0",
            device_scale_factor=2,
        )

        page = context.new_page()

        # Inject Telegram WebApp mock before scripts load
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

        # 1. Screen 1: Home Screen
        page.goto(f"{BASE_URL}/", wait_until="networkidle")
        page.wait_for_timeout(1000)
        home_path = OUTPUT_DIR / "01_home_screen.png"
        page.screenshot(path=str(home_path))
        print(f"Captured: {home_path}")

        # 2. Screen 2: Product Detail Screen
        page.goto(f"{BASE_URL}/?product=1", wait_until="networkidle")
        page.wait_for_timeout(1000)
        prod_path = OUTPUT_DIR / "02_product_screen.png"
        page.screenshot(path=str(prod_path))
        print(f"Captured: {prod_path}")

        # 3. Add to cart & capture Screen 3: Bag Screen
        # Let's add product 1 to cart via API first so the cart has items
        import urllib.request
        req = urllib.request.Request(
            f"{BASE_URL}/api/cart",
            data=json.dumps({"product_id": 1, "size": "M", "color": "Sakura pushti 🌸", "qty": 1}).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Telegram-Init-Data": admin_init_data},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                pass
        except Exception as e:
            print("Cart add error:", e)

        page.goto(f"{BASE_URL}/?tab=bag", wait_until="networkidle")
        page.wait_for_timeout(1000)
        bag_path = OUTPUT_DIR / "03_bag_screen.png"
        page.screenshot(path=str(bag_path))
        print(f"Captured: {bag_path}")

        # 4. Screen 4: Admin Dashboard
        page.goto(f"{BASE_URL}/?tab=admin", wait_until="networkidle")
        page.wait_for_timeout(1200)
        admin_path = OUTPUT_DIR / "04_admin_screen.png"
        page.screenshot(path=str(admin_path))
        print(f"Captured: {admin_path}")

        browser.close()

    print("All screenshots successfully captured!")


if __name__ == "__main__":
    main()
