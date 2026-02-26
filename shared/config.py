import json
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
RIGHTMOVE_LOCATION_ID = get_env("RIGHTMOVE_LOCATION_ID", "STATION^3509")
SEARCH_RADIUS_MILES = float(get_env("SEARCH_RADIUS_MILES", "1.0"))
MAX_RENT_PCM = int(get_env("MAX_RENT_PCM", "2200"))
MIN_BEDROOMS = int(get_env("MIN_BEDROOMS", "1"))
MAX_BEDROOMS = int(get_env("MAX_BEDROOMS", "2"))

# Zones
ZONES_FILE = Path(get_env("ZONES_FILE", "/app/config/zones.json"))

def load_zones(zones_file: Path | None = None) -> list[dict]:
    path = zones_file or ZONES_FILE
    if path.exists():
        with open(path) as f:
            return json.load(f)
    # Fallback to legacy env vars
    return [{
        "name": "Default",
        "rightmove_id": RIGHTMOVE_LOCATION_ID,
        "openrent_term": "Finchley Road Station",
        "radius_miles": SEARCH_RADIUS_MILES,
        "lat": 51.5472,
        "lng": -0.1803,
    }]
