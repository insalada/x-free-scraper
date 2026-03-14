"""x-free-scraper — Public API.

Two public functions:

    scrape_accounts(usernames, hours_lookback=24) -> list[dict]
        Scrape recent posts from one or more X accounts.

    refresh_session(push_url=None, api_key=None) -> None
        Open a browser for manual login and save the session cookies locally.
        Optionally push them to a remote endpoint.

Quick start:

    from x_scraper import scrape_accounts, refresh_session

    # First time (or when your session expires):
    refresh_session()

    # Then scrape:
    posts = scrape_accounts(["elonmusk", "sama"], hours_lookback=48)
    for post in posts:
        print(post["username"], post["posted_at"], post["content"][:80])
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from x_scraper.config import settings
from x_scraper.scraper import scrape_account
from x_scraper.session import _capture_session, _push_to_remote, _save_locally

__all__ = ["scrape_accounts", "refresh_session"]


def scrape_accounts(
    usernames: list[str],
    hours_lookback: int | None = None,
) -> list[dict]:
    """Scrape recent posts from one or more X accounts.

    Args:
        usernames: List of X usernames (without @).
        hours_lookback: How many hours back to look for posts.
            Defaults to the HOURS_LOOKBACK env variable (24 h if not set).

    Returns:
        Combined list of post dicts, each containing:
            - x_id (str): Unique tweet ID.
            - content (str): Full tweet text.
            - username (str): Account username.
            - posted_at (str): ISO 8601 timestamp (UTC).
            - likes (int)
            - retweets (int)
            - replies (int)
    """
    all_posts: list[dict] = []
    for username in usernames:
        posts = scrape_account(username, hours_lookback=hours_lookback)
        all_posts.extend(posts)
    return all_posts


def refresh_session(push_url: str | None = None, api_key: str | None = None) -> None:
    """Open a browser, let you log into X manually, and save the session cookies.

    After a successful login the cookies are written to the path configured by
    SESSION_STORAGE_PATH (default: x_session.json next to this package).

    Args:
        push_url: Optional base URL of a remote admin API that accepts the
            session via POST /session/refresh. Useful for refreshing a
            production deployment without logging into the server.
        api_key: Optional API key sent as the X-API-Key header when pushing
            to a remote endpoint.
    """
    session_path = Path(settings.session_storage_path)
    cookies = asyncio.run(_capture_session())
    _save_locally(cookies, session_path)
    if push_url:
        _push_to_remote(cookies, push_url, api_key=api_key)
