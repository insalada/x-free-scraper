"""CLI entry points for x-free-scraper.

Usage:
    # Scrape one or more accounts:
    python -m x_scraper scrape elonmusk sama --hours 48

    # Refresh your session cookies (opens a browser):
    python -m x_scraper refresh-session
    python -m x_scraper refresh-session --push https://your-app.com --api-key secret
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

import structlog


def _configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(level),
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
    )


def cmd_scrape(args: argparse.Namespace) -> None:
    from x_scraper import scrape_accounts

    posts = scrape_accounts(args.usernames, hours_lookback=args.hours)
    if args.output == "json":
        print(json.dumps(posts, indent=2, ensure_ascii=False))
    else:
        for p in posts:
            print(f"[@{p['username']}] {p['posted_at']}  ❤ {p['likes']}  🔁 {p['retweets']}")
            print(f"  {p['content'][:200]}")
            print()


def cmd_refresh_session(args: argparse.Namespace) -> None:
    from x_scraper import refresh_session

    refresh_session(push_url=args.push, api_key=args.api_key)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="x_scraper",
        description="X (Twitter) free scraper — scrape accounts or refresh your session.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    # --- scrape sub-command ---
    scrape_p = sub.add_parser("scrape", help="Scrape posts from one or more X accounts")
    scrape_p.add_argument("usernames", nargs="+", metavar="USERNAME", help="X username(s) without @")
    scrape_p.add_argument(
        "--hours",
        type=int,
        default=None,
        metavar="N",
        help="How many hours back to look (default: HOURS_LOOKBACK env var or 24)",
    )
    scrape_p.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    # --- refresh-session sub-command ---
    session_p = sub.add_parser("refresh-session", help="Capture and save an X browser session")
    session_p.add_argument(
        "--push",
        metavar="ADMIN_URL",
        default=None,
        help="Also push the session to a remote admin API at this base URL",
    )
    session_p.add_argument(
        "--api-key",
        metavar="KEY",
        default=None,
        help="API key for the remote admin endpoint (X-API-Key header)",
    )

    args = parser.parse_args()
    _configure_logging(debug=args.debug)

    if args.command == "scrape":
        cmd_scrape(args)
    elif args.command == "refresh-session":
        cmd_refresh_session(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
