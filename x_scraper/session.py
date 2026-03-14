"""Session capture and refresh utilities for X (Twitter).

Internal module — use the public API in x_scraper/__init__.py instead.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import structlog

from x_scraper.config import settings

logger = structlog.get_logger()

STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-infobars",
    "--disable-dev-shm-usage",
]


async def _capture_session() -> list:
    """Open a real (non-headless) browser, wait for the user to log in manually,
    then capture and return the resulting cookies."""
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            channel="chrome",
            args=STEALTH_ARGS,
        )
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        page = await context.new_page()
        await page.goto("https://x.com/login")

        print("\n=== Log into X in the browser window that just opened. ===")
        print("=== When you see your home feed, press Enter here.      ===\n")
        input()

        cookies = await context.cookies()
        await browser.close()
        return cookies


def _save_locally(cookies: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cookies, indent=2))
    logger.info("session_saved_locally", path=str(path), cookies=len(cookies))
    print(f"Session saved → {path}  ({len(cookies)} cookies)")


def _push_to_remote(cookies: list, base_url: str, api_key: str | None = None) -> None:
    """Push the captured cookies to a remote admin API (optional)."""
    url = base_url.rstrip("/") + "/session/refresh"
    payload = json.dumps(cookies).encode()
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    response = httpx.post(
        url,
        headers=headers,
        files={"file": ("x_session.json", payload, "application/json")},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    logger.info("session_pushed_to_remote", url=url, response=data)
    print(f"Session pushed to remote → {url}  (response: {data})")
