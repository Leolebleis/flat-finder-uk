import os
from pathlib import Path


def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# Paths
DB_PATH = Path(get_env("FLAT_FINDER_DB", "/app/data/flat_finder.db"))

# Notifications
NTFY_TOPIC = get_env("NTFY_TOPIC", "")
GMAIL_ADDRESS = get_env("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = get_env("GMAIL_APP_PASSWORD", "")

# Search parameters
MAX_RENT_PCM = int(get_env("MAX_RENT_PCM", "2200"))
MIN_BEDROOMS = int(get_env("MIN_BEDROOMS", "1"))
MAX_BEDROOMS = int(get_env("MAX_BEDROOMS", "2"))

# Scraping: MCP endpoint of a running scrapling container; empty = fetch directly
SCRAPLING_MCP_URL = get_env("SCRAPLING_MCP_URL")

# How often to re-notify about a source that is still failing. 0 disables
# re-alerts (first-failure and recovery pushes always fire).
SCRAPER_REALERT_HOURS = float(get_env("SCRAPER_REALERT_HOURS", "24"))

# Security
SECRET_KEY = get_env("SECRET_KEY", "dev-secret-change-in-production")
