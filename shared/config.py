import os
from pathlib import Path

def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)

# Paths
DB_PATH = Path(get_env("FLAT_FINDER_DB", "/home/dev/projects/flat-finder/flat_finder.db"))

# API
API_KEY = get_env("FLAT_FINDER_API_KEY", "")
API_BASE_URL = get_env("FLAT_FINDER_API_URL", "https://disqt.com/flat/api")

# Notifications
NTFY_TOPIC = get_env("NTFY_TOPIC", "")
GMAIL_ADDRESS = get_env("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = get_env("GMAIL_APP_PASSWORD", "")

# Search parameters
RIGHTMOVE_LOCATION_ID = get_env("RIGHTMOVE_LOCATION_ID", "REGION^61294")
SEARCH_RADIUS_MILES = float(get_env("SEARCH_RADIUS_MILES", "1.0"))
MAX_RENT_PCM = int(get_env("MAX_RENT_PCM", "2200"))
MIN_BEDROOMS = int(get_env("MIN_BEDROOMS", "1"))
MAX_BEDROOMS = int(get_env("MAX_BEDROOMS", "2"))
