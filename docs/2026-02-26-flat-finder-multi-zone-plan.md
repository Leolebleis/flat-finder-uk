# Multi-Zone Search & Commute Time Implementation Plan — COMPLETED

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add multi-zone search (configurable via JSON) and TfL commute time display to flat-finder.

**Architecture:** Zone config loaded from `zones.json` mounted into the scraper container. Scraper iterates zones, tags listings, fetches commute time from TfL API for new listings. UI adds zone filter buttons and commute badge.

**Tech Stack:** Python/FastAPI, SQLite (ALTER TABLE migration), TfL Journey Planner API (free, no key), Jinja2 templates.

---

### Task 1: DB Migration -- Add zone and commute_mins columns

**Files:**
- Modify: `shared/models.py`
- Modify: `tests/test_models.py`

**Step 1: Update test to expect new columns**

In `tests/test_models.py`, update `test_listings_table_has_expected_columns` to include `"zone"` and `"commute_mins"` in the `expected` set.

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_models.py::test_listings_table_has_expected_columns -v`
Expected: FAIL -- missing `zone` and `commute_mins`

**Step 3: Add columns to schema and migration**

In `shared/models.py`:
- Add `zone TEXT,` and `commute_mins INTEGER,` to `LISTINGS_SCHEMA` (before `first_seen`)
- Add migration logic to `init_db()` that runs `ALTER TABLE listings ADD COLUMN zone TEXT` and `ALTER TABLE listings ADD COLUMN commute_mins INTEGER` wrapped in try/except (column may already exist)
- Add `zone` and `commute_mins` to the column list in `insert_listing()`

**Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: ALL PASS

**Step 5: Commit**

```
git add shared/models.py tests/test_models.py
git commit -m "feat: add zone and commute_mins columns to listings"
```

---

### Task 2: Zone config loader

**Files:**
- Modify: `shared/config.py`
- Create: `zones.json` (in project root, for default config)
- Create: `tests/test_zones.py`

**Step 1: Write test for zone loading**

Create `tests/test_zones.py`:

```python
import json
import tempfile
from pathlib import Path
from shared.config import load_zones

def test_load_zones_from_file():
    zones = [
        {"name": "Finchley Road", "rightmove_id": "STATION^3509",
         "openrent_term": "Finchley Road Station", "radius_miles": 1.0,
         "lat": 51.5472, "lng": -0.1803},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(zones, f)
        f.flush()
        result = load_zones(Path(f.name))
    assert len(result) == 1
    assert result[0]["name"] == "Finchley Road"
    assert result[0]["rightmove_id"] == "STATION^3509"

def test_load_zones_fallback_when_file_missing():
    result = load_zones(Path("/nonexistent/zones.json"))
    assert len(result) == 1
    assert result[0]["name"] == "Default"
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_zones.py -v`
Expected: FAIL -- `load_zones` not found

**Step 3: Implement zone loader**

In `shared/config.py`:
- Add `import json`
- Add `ZONES_FILE = Path(get_env("ZONES_FILE", "/app/config/zones.json"))`
- Add function:

```python
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
```

**Step 4: Create default zones.json**

Create `zones.json` in project root:

```json
[
  {
    "name": "Finchley Road",
    "rightmove_id": "STATION^3509",
    "openrent_term": "Finchley Road Station",
    "radius_miles": 1.0,
    "lat": 51.5472,
    "lng": -0.1803
  },
  {
    "name": "St John's Wood",
    "rightmove_id": "STATION^8627",
    "openrent_term": "St John's Wood Station",
    "radius_miles": 0.75,
    "lat": 51.5347,
    "lng": -0.1743
  }
]
```

**Step 5: Run tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: ALL PASS

**Step 6: Commit**

```
git add shared/config.py zones.json tests/test_zones.py
git commit -m "feat: zone config loader with JSON file and env var fallback"
```

---

### Task 3: TfL commute time fetcher

**Files:**
- Create: `scraper/commute.py`
- Create: `tests/test_commute.py`

**Step 1: Write test**

Create `tests/test_commute.py`:

```python
from unittest.mock import patch, MagicMock
from scraper.commute import get_commute_mins

def test_get_commute_mins_returns_shortest():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "journeys": [
            {"duration": 45},
            {"duration": 32},
            {"duration": 50},
        ]
    }
    with patch("scraper.commute.requests.get", return_value=mock_resp) as mock_get:
        result = get_commute_mins(51.5472, -0.1803)
    assert result == 32
    # Verify TfL API was called with correct params
    call_url = mock_get.call_args[0][0]
    assert "51.5472,-0.1803" in call_url
    assert "51.4875,-0.1827" in call_url

def test_get_commute_mins_returns_none_on_error():
    with patch("scraper.commute.requests.get", side_effect=Exception("timeout")):
        result = get_commute_mins(51.5472, -0.1803)
    assert result is None

def test_get_commute_mins_returns_none_for_no_journeys():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"journeys": []}
    with patch("scraper.commute.requests.get", return_value=mock_resp):
        result = get_commute_mins(51.5472, -0.1803)
    assert result is None
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_commute.py -v`
Expected: FAIL -- `scraper.commute` not found

**Step 3: Implement**

Create `scraper/commute.py`:

```python
import logging
import requests

log = logging.getLogger("flat-finder")

DESTINATION_LAT = 51.4875
DESTINATION_LNG = -0.1827
TFL_MODES = "tube,bus,overground,elizabeth-line,dlr,tram"

def get_commute_mins(lat: float, lng: float) -> int | None:
    url = f"https://api.tfl.gov.uk/Journey/JourneyResults/{lat},{lng}/to/{DESTINATION_LAT},{DESTINATION_LNG}"
    try:
        resp = requests.get(url, params={
            "mode": TFL_MODES,
            "time": "0830",
            "timeIs": "arriving",
        }, timeout=15)
        resp.raise_for_status()
        journeys = resp.json().get("journeys", [])
        if not journeys:
            return None
        return min(j["duration"] for j in journeys)
    except Exception as e:
        log.error(f"TfL commute lookup failed: {e}")
        return None
```

**Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: ALL PASS

**Step 5: Commit**

```
git add scraper/commute.py tests/test_commute.py
git commit -m "feat: TfL commute time fetcher"
```

---

### Task 4: Update scraper to iterate zones and fetch commute

**Files:**
- Modify: `scraper/scraper.py`
- Modify: `tests/test_scraper.py`

**Step 1: Update test helper and add zone test**

In `tests/test_scraper.py`, add `"zone": None, "commute_mins": None` to `_make_listing()` return dict.

Add test:

```python
def test_process_new_listings_preserves_zone():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = get_connection(db_path)
        listing = _make_listing("rightmove_1")
        listing["zone"] = "St John's Wood"
        new = process_new_listings(conn, [listing])
        assert len(new) == 1
        row = conn.execute("SELECT zone FROM listings WHERE id = ?", ("rightmove_1",)).fetchone()
        assert row["zone"] == "St John's Wood"
        conn.close()
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_scraper.py -v`
Expected: FAIL -- zone column missing from INSERT or not in listing dict

**Step 3: Rewrite scraper `run()` to iterate zones**

In `scraper/scraper.py`:
- Replace import of `RIGHTMOVE_LOCATION_ID, SEARCH_RADIUS_MILES` with `load_zones`
- Add import of `get_commute_mins` from `scraper.commute`
- Rewrite `run()`:

```python
def run() -> None:
    init_db(DB_PATH)
    conn = get_connection(DB_PATH)
    first_run = is_first_run(conn)
    zones = load_zones()

    all_listings = []
    seen_ids = set()

    for zone in zones:
        rm_listings, rm_error = _scrape_source(
            f"rightmove/{zone['name']}",
            lambda z=zone: fetch_rightmove(z["rightmove_id"], z["radius_miles"],
                                           MIN_BEDROOMS, MAX_BEDROOMS, MAX_RENT_PCM),
            conn,
        )
        or_listings, or_error = _scrape_source(
            f"openrent/{zone['name']}",
            lambda z=zone: fetch_openrent(z["openrent_term"], z["radius_miles"],
                                          MIN_BEDROOMS, MAX_BEDROOMS, MAX_RENT_PCM),
            conn,
        )

        _handle_failure_state(conn, f"rightmove/{zone['name']}", rm_error)
        _handle_failure_state(conn, f"openrent/{zone['name']}", or_error)

        for listing in rm_listings + or_listings:
            if listing["id"] not in seen_ids:
                listing["zone"] = zone["name"]
                all_listings.append(listing)
                seen_ids.add(listing["id"])

    new_listings = process_new_listings(conn, all_listings)

    # Fetch commute time for new listings with coordinates
    for listing in new_listings:
        if listing.get("latitude") and listing.get("longitude"):
            mins = get_commute_mins(listing["latitude"], listing["longitude"])
            if mins is not None:
                listing["commute_mins"] = mins
                conn.execute("UPDATE listings SET commute_mins = ? WHERE id = ?",
                             (mins, listing["id"]))
                conn.commit()

    # Push all scraped listings to VPS API (dedup handled server-side)
    if all_listings:
        _push_to_api(all_listings)

    if first_run:
        set_state(conn, "initialised", "true")
        log.info(f"First run: found {len(all_listings)} existing listings")
        if NTFY_TOPIC:
            _notify_safe(send_ntfy, NTFY_TOPIC, "Flat Finder initialised",
                         f"Found {len(all_listings)} existing listings across {len(zones)} zones.")
    elif new_listings:
        log.info(f"Found {len(new_listings)} new listings")
        if NTFY_TOPIC:
            title, body = format_ntfy_message(new_listings)
            _notify_safe(send_ntfy, NTFY_TOPIC, title, body)
        if GMAIL_ADDRESS and GMAIL_APP_PASSWORD:
            html = format_email_html(new_listings)
            _notify_safe(send_email, GMAIL_ADDRESS, GMAIL_APP_PASSWORD,
                         f"Flat Finder: {len(new_listings)} new listing{'s' if len(new_listings) != 1 else ''}",
                         html)
    else:
        log.info("No new listings found")

    conn.close()
```

**Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: ALL PASS

**Step 5: Commit**

```
git add scraper/scraper.py tests/test_scraper.py
git commit -m "feat: scraper iterates zones and fetches commute times"
```

---

### Task 5: UI -- Zone filter and commute badge

**Files:**
- Modify: `ui/main.py`
- Modify: `ui/templates/feed.html`
- Modify: `ui/templates/detail.html`

**Step 1: Update feed endpoint**

In `ui/main.py`:
- Add `zone` query parameter to `feed_page()`: `zone: str = "all"`
- After fetching rows, collect unique zones: `zones = sorted(set(d.get("zone") or "Unknown" for d in listings))`
- Filter listings by zone if `zone != "all"`: `listings = [l for l in listings if (l.get("zone") or "Unknown") == zone]`
- Add `"commute"` to `SORT_OPTIONS`: `"commute": "Commute (shortest)"`
- Add commute sort to `_sort_listings()`: `elif sort == "commute": return sorted(listings, key=lambda l: (l.get("commute_mins") is None, l.get("commute_mins") or 999))`
- Pass `zones` and `zone` to template context
- Update the sort select `onchange` to preserve zone param: `window.location.href='?sort='+this.value+'&zone={{ zone }}'`

**Step 2: Update feed template**

In `ui/templates/feed.html`, add zone filter buttons after the Favourites button:

```html
<span class="filter-separator"></span>
<a class="filter-btn {% if zone == 'all' %}filter-btn--active{% endif %}"
   href="?sort={{ sort }}&zone=all">All Zones</a>
{% for z in zones %}
<a class="filter-btn {% if zone == z %}filter-btn--active{% endif %}"
   href="?sort={{ sort }}&zone={{ z }}">{{ z }}</a>
{% endfor %}
```

Add commute badge to the card meta section (after the distance badge):

```html
{% if l.commute_mins is not none %}
<span class="meta-badge meta-badge--commute">{{ l.commute_mins }} min</span>
{% endif %}
```

Update the sort select to preserve zone:

```html
<select class="sort-select" onchange="window.location.href='?sort='+this.value+'&zone={{ zone }}'">
```

**Step 3: Update detail template**

In `ui/templates/detail.html`, add commute and zone badges to `detail__meta`:

```html
{% if listing.commute_mins is not none %}
<span class="meta-badge meta-badge--commute">{{ listing.commute_mins }} min to Chelsea</span>
{% endif %}
{% if listing.zone %}
<span class="meta-badge">{{ listing.zone }}</span>
{% endif %}
```

**Step 4: Add CSS for filter separator and commute badge**

In `ui/static/style.css`:

```css
.filter-separator {
  width: 1px;
  height: 24px;
  background: var(--border);
  align-self: center;
}

.meta-badge--commute {
  background: #e3f0ff;
  color: #0051a8;
}
```

**Step 5: Run tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: ALL PASS

**Step 6: Commit**

```
git add ui/main.py ui/templates/feed.html ui/templates/detail.html ui/static/style.css
git commit -m "feat: zone filter, commute badge, and commute sort in UI"
```

---

### Task 6: Docker config and deployment

**Files:**
- Create: `config/flat-finder/zones.json` (on Pi at `/opt/mediastack/config/flat-finder/zones.json`)
- Modify: Docker compose in `/opt/mediastack/docker-compose.yml`
- Modify: `scraper/Dockerfile`

**Step 1: Create zones.json on Pi**

```bash
sudo mkdir -p /opt/mediastack/config/flat-finder
```

Write `/opt/mediastack/config/flat-finder/zones.json` with the two zones (Finchley Road + St John's Wood).

**Step 2: Update Docker compose**

Add volume mount to `flat-finder-scraper` service:

```yaml
    volumes:
      - flat-finder-scraper-data:/app/data
      - ./config/flat-finder/zones.json:/app/config/zones.json:ro
```

**Step 3: Update VPS**

```bash
ssh dev "cd /home/dev/projects/flat-finder && git pull && sudo systemctl restart flat-finder-api.service"
```

**Step 4: Rebuild and restart Pi containers**

```bash
cd /opt/mediastack
docker compose up -d --build flat-finder flat-finder-scraper
docker compose restart nginx
```

**Step 5: Verify**

- Check scraper logs: `docker logs flat-finder-scraper`
- Verify both zones scraped and commute times populated
- Check UI at http://raspberrypi/flat/ -- should show zone filter buttons and commute badges
- Check VPS API: `curl -s -H "X-API-Key: <key>" https://disqt.com/flat/api/stats`

**Step 6: Commit any remaining changes**

```
git add -A && git commit -m "feat: multi-zone deployment config" && git push
```

---

### Task 7: Backfill commute times for existing listings

**Step 1: Run a one-off script inside the scraper container**

```bash
docker exec flat-finder-scraper python3 -c "
from shared.models import get_connection
from scraper.commute import get_commute_mins
from pathlib import Path
import time

conn = get_connection(Path('/app/data/scraper.db'))
rows = conn.execute('SELECT id, latitude, longitude FROM listings WHERE commute_mins IS NULL AND latitude IS NOT NULL').fetchall()
print(f'Backfilling {len(rows)} listings')
for row in rows:
    mins = get_commute_mins(row['latitude'], row['longitude'])
    if mins is not None:
        conn.execute('UPDATE listings SET commute_mins = ? WHERE id = ?', (mins, row['id']))
        conn.commit()
        print(f'  {row[\"id\"]}: {mins} min')
    time.sleep(0.2)  # Rate limit courtesy
print('Done')
"
```

**Step 2: Push updated listings to VPS**

The next scraper run will push all listings (including updated commute_mins) to VPS. Or trigger manually:

```bash
docker restart flat-finder-scraper
```

**Step 3: Verify in UI**

Check http://raspberrypi/flat/?sort=commute -- listings should sort by commute time.
