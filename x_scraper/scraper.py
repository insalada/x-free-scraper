"""Core Playwright-based scraper for X (Twitter) profiles.

Internal module — use the public API in x_scraper/__init__.py instead.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog
from playwright.async_api import Page, async_playwright

from x_scraper.config import settings

logger = structlog.get_logger()

STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-infobars",
    "--disable-dev-shm-usage",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _session_file() -> Path:
    return Path(settings.session_storage_path)


def _parse_count(label: str) -> int:
    """Parse a stat count from an aria-label like '1,234 Likes' or '12K Likes'."""
    match = re.match(r"([\d,]+\.?\d*)([KkMm]?)", label.strip())
    if not match:
        return 0
    num = float(match.group(1).replace(",", ""))
    suffix = match.group(2).upper()
    if suffix == "K":
        num *= 1_000
    elif suffix == "M":
        num *= 1_000_000
    return int(num)


async def _extract_stat(tweet_el, testid: str) -> int:
    """Extract a numeric stat from a tweet element's button aria-label."""
    try:
        btn = await tweet_el.query_selector(f'[data-testid="{testid}"]')
        if not btn:
            return 0
        label = await btn.get_attribute("aria-label") or ""
        return _parse_count(label)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


async def _login(page: Page, username: str, password: str, email: str | None = None) -> None:
    """Log into X using the standard login flow.

    Handles the optional intermediate 'confirm your identity' step that X
    sometimes inserts between the username and password screens.
    The challenge expects the account email or phone number (set X_EMAIL in .env).
    """
    logger.info("login_start")
    await page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded")
    await page.wait_for_timeout(1_500)

    # Step 1: username — type slowly to avoid bot detection
    username_input = await page.wait_for_selector('input[autocomplete="username"]', timeout=15_000)
    await username_input.click()
    await page.keyboard.type(username, delay=80)
    await page.wait_for_timeout(500)
    await page.keyboard.press("Enter")

    # Step 2: X sometimes asks to confirm identity (email/phone) before password
    try:
        await page.wait_for_selector('input[name="password"]', timeout=6_000)
    except Exception:
        confirm_sel = 'input[data-testid="ocfEnterTextTextInput"], input[name="text"]'
        confirm_el = await page.query_selector(confirm_sel)
        if confirm_el:
            challenge_value = email or username
            logger.info("login_identity_challenge", filling_with="email" if email else "username")
            await confirm_el.click()
            await page.keyboard.type(challenge_value, delay=80)
            await page.wait_for_timeout(500)
            await page.keyboard.press("Enter")
        await page.wait_for_selector('input[name="password"]', timeout=10_000)

    # Step 3: password
    await page.wait_for_timeout(500)
    password_input = await page.query_selector('input[name="password"]')
    await password_input.click()
    await page.keyboard.type(password, delay=80)
    await page.wait_for_timeout(500)
    await page.keyboard.press("Enter")
    await page.wait_for_url(re.compile(r"x\.com/home"), timeout=20_000)
    logger.info("login_done")


# ---------------------------------------------------------------------------
# Profile scraping
# ---------------------------------------------------------------------------


async def _scrape_profile(username: str, cutoff: datetime, headless: bool = True) -> list[dict]:
    """Use Playwright to scrape an X profile page and return posts newer than cutoff."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            channel="chrome",
            args=STEALTH_ARGS,
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # Load saved session if available, otherwise fall back to credential login
        session_file = _session_file()
        if session_file.exists():
            cookies = json.loads(session_file.read_text())
            await context.add_cookies(cookies)
            logger.info("session_loaded", file=str(session_file))
        elif settings.x_username and settings.x_password:
            page = await context.new_page()
            await _login(page, settings.x_username, settings.x_password, email=settings.x_email)
            await page.close()
        else:
            logger.warning("no_session_and_no_credentials_scraping_without_login")

        page = await context.new_page()

        logger.info("navigating_to_profile", username=username)
        await page.goto(f"https://x.com/{username}", wait_until="domcontentloaded")
        await page.wait_for_selector('[data-testid="tweet"]', timeout=30_000)

        posts: list[dict] = []
        seen_ids: set[str] = set()
        stale_scrolls = 0

        while stale_scrolls < 4:
            tweet_elements = await page.query_selector_all('[data-testid="tweet"]')
            logger.debug("tweet_elements_found", count=len(tweet_elements), scroll=stale_scrolls)
            new_count = 0
            reached_cutoff = False

            for tweet_el in tweet_elements:
                # tweet ID via permalink
                link_el = await tweet_el.query_selector('a[href*="/status/"]')
                if not link_el:
                    continue
                href = await link_el.get_attribute("href") or ""
                x_id = href.rstrip("/").split("/")[-1]
                if not x_id.isdigit():
                    continue
                if x_id in seen_ids:
                    continue
                seen_ids.add(x_id)

                # timestamp (Twitter emits ISO 8601 in datetime attribute)
                time_el = await tweet_el.query_selector("time[datetime]")
                if not time_el:
                    continue
                dt_str = await time_el.get_attribute("datetime") or ""
                try:
                    posted_at = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                except ValueError:
                    continue

                if posted_at < cutoff:
                    reached_cutoff = True
                    break

                # text
                text_el = await tweet_el.query_selector('[data-testid="tweetText"]')
                content = (await text_el.inner_text() if text_el else "").strip()
                if not content:
                    continue

                new_count += 1

                likes = await _extract_stat(tweet_el, "like")
                retweets = await _extract_stat(tweet_el, "retweet")
                replies = await _extract_stat(tweet_el, "reply")

                posts.append(
                    {
                        "x_id": x_id,
                        "content": content,
                        "username": username,
                        "posted_at": posted_at.isoformat(),
                        "likes": likes,
                        "retweets": retweets,
                        "replies": replies,
                    }
                )
                logger.debug("post_collected", x_id=x_id, content_len=len(content))

            if reached_cutoff:
                break

            stale_scrolls = 0 if new_count > 0 else stale_scrolls + 1
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2_000)

        try:
            await asyncio.wait_for(browser.close(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("browser_close_timeout_forcing_exit")

        return posts


# ---------------------------------------------------------------------------
# Public scraping entrypoint
# ---------------------------------------------------------------------------


def scrape_account(username: str, hours_lookback: int | None = None) -> list[dict]:
    """Scrape posts from a single X account published within the last *hours_lookback* hours.

    Args:
        username: X (Twitter) username without the @ symbol.
        hours_lookback: How far back to look for posts. Defaults to the value
            set in the HOURS_LOOKBACK env var (24 h if not set).

    Returns:
        List of dicts with keys: x_id, content, username, posted_at,
        likes, retweets, replies.
    """
    lookback = hours_lookback if hours_lookback is not None else settings.hours_lookback
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=lookback)
    logger.info("scraping_start", username=username, cutoff=cutoff.isoformat())
    posts = asyncio.run(_scrape_profile(username, cutoff, headless=settings.scraper_headless))
    logger.info("scraping_done", username=username, count=len(posts))
    return posts
