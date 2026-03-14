# X Free Scraper

A lightweight Python library for scraping public posts from X (Twitter) profiles using Playwright — no official API key required.

## Features

- Scrape posts from one or multiple X accounts with a single function call
- Configurable lookback window (e.g. last 24 hours, last 7 days)
- Cookie-based session management to avoid login walls
- Manual session capture via a real browser window
- Optional remote session push (useful for refreshing production deployments)
- Headless or headed browser mode

## Installation

### 1. Clone and set up the environment

```bash
git clone https://github.com/your-username/x-free-scraper.git
cd x-free-scraper

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env as needed
```

See [.env.example](.env.example) for all available options.

## Quick start

### Capture a session (first time or when expired)

The scraper relies on saved browser cookies to authenticate. Run the session
capture once and log in manually in the browser window that opens:

```bash
python -m x_scraper refresh-session
```

This saves a `x_session.json` file in the project root. The file contains your
authentication cookies — **keep it secret and never commit it to git**.

### Scrape accounts from the CLI

```bash
# Scrape a single account (last 24 hours by default):
python -m x_scraper scrape elonmusk

# Scrape multiple accounts, look back 48 hours, output JSON:
python -m x_scraper scrape elonmusk sama --hours 48 --output json
```

### Use as a library

```python
from x_scraper import scrape_accounts, refresh_session

# First time / when session expires:
refresh_session()

# Scrape one or more accounts:
posts = scrape_accounts(["elonmusk", "sama"], hours_lookback=48)

for post in posts:
    print(f"[@{post['username']}] {post['posted_at']}")
    print(f"  {post['content']}")
    print(f"  ❤ {post['likes']}  🔁 {post['retweets']}  💬 {post['replies']}")
    print()
```

### Post schema

Each item in the returned list is a dict with the following keys:

| Key | Type | Description |
|---|---|---|
| `x_id` | str | Unique tweet ID |
| `content` | str | Full tweet text |
| `username` | str | Account username (without @) |
| `posted_at` | str | ISO 8601 UTC timestamp |
| `likes` | int | Like count |
| `retweets` | int | Retweet count |
| `replies` | int | Reply count |

## Session management

### Refresh a local session

```bash
python -m x_scraper refresh-session
```

### Refresh a remote / production session

If you run this scraper on a server, you can refresh the session from your
local machine and push the new cookies to the remote instance:

```bash
python -m x_scraper refresh-session --push https://your-app.com --api-key YOUR_KEY
```

This POSTs the cookies to `https://your-app.com/session/refresh` with the
`X-API-Key` header. The remote server is responsible for storing the file.

### Programmatic session refresh

```python
from x_scraper import refresh_session

# Save locally only:
refresh_session()

# Save locally and push to a remote endpoint:
refresh_session(push_url="https://your-app.com", api_key="secret")
```

## Configuration

All settings are read from environment variables (or a `.env` file):

| Variable | Default | Description |
|---|---|---|
| `SESSION_STORAGE_PATH` | `x_session.json` | Path to the session cookie file |
| `HOURS_LOOKBACK` | `24` | Default lookback window in hours |
| `SCRAPER_HEADLESS` | `true` | Run browser headlessly |
| `X_USERNAME` | — | Fallback login username (if no session file) |
| `X_EMAIL` | — | Fallback login email (identity challenge) |
| `X_PASSWORD` | — | Fallback login password (if no session file) |

## How it works

1. **Session loading** — On startup the scraper reads `x_session.json` and injects the cookies into a fresh Playwright browser context. This lets it access authenticated X pages without re-logging in every run.
2. **Profile navigation** — It navigates to `https://x.com/<username>` and waits for tweets to render.
3. **Infinite scroll** — It scrolls the page, collecting tweets until it either reaches the configured time cutoff or hits 4 consecutive scroll cycles with no new posts.
4. **Data extraction** — For each tweet it extracts: tweet ID (from the permalink), timestamp (from the `<time datetime>` attribute), full text, and engagement stats (likes, retweets, replies).

## Limitations

- Only scrapes the public timeline of an account (no private accounts, no DMs).
- Relies on X's current HTML structure — may break if X changes their frontend significantly.
- Subject to X's rate limiting and anti-bot measures. Use reasonable lookback windows and avoid scraping too many accounts in rapid succession.
- Session cookies expire periodically. Re-run `refresh-session` when you start getting login walls.

## License

MIT
