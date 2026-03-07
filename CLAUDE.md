# Flat Finder

Property alert system. Scrapes Rightmove + OpenRent, displays listings in a local web UI.

Design docs: `../../docs/plans/2026-02-26-flat-finder-design.md`, `../../docs/plans/2026-02-26-flat-finder-scoring-design.md`, `docs/2026-03-07-flat-finder-poi-design.md`

## Structure
- Everything runs on Pi as Docker containers via its own `docker-compose.yml` (separate from mediastack)
- `scraper/` and `ui/` share the same SQLite DB via `flat-finder-data` volume (WAL mode)
- `shared/` (models, config, geo) used by both components
- External `flat-finder-net` Docker network bridges nginx (mediastack) to the flat-finder UI
- Zone config: `/opt/mediastack/config/flat-finder/zones.json` (mounted read-only into scraper)

## Components
- **scraper/** -- Rightmove + OpenRent scrapers, iterates zones, fetches TfL commute times for all POIs for new listings. Cross-source dedup by address+price+bedrooms. Runs every 15 min.
- **ui/** -- FastAPI + Jinja2. Redesigned "Warm Minimal" UI (Bricolage Grotesque + DM Sans, teal accent). Feed with zone filter, weighted scoring, seen/favourite/notes, label overrides. Dark mode via prefers-color-scheme.
- **shared/models.py** -- SQLite schema (listings, pois, poi_commutes), migrations, insert/query helpers
- **shared/config.py** -- env var config + `load_zones()` from JSON
- **shared/geo.py** -- Google Maps URL parser (extracts lat/lng from full URLs and short links)

## Key commands
- Rebuild: `docker compose up -d --build` (from this directory)
- Scraper logs: `docker logs flat-finder-scraper`
- UI logs: `docker logs flat-finder`
- UI URL: https://raspberrypi/flat/
- Run tests: `.venv/bin/python -m pytest tests/ -v`

## Key coordinates
- **Places of Interest**: User-configurable via Settings page (`/flat/settings`). Stored in `pois` table. Commute times in `poi_commutes` table.
- **Finchley Road Station** (station distance, haversine): 51.5472, -0.1803 -- in `ui/main.py`

## Features
- **Dynamic POIs**: User-configurable Places of Interest via Settings page. Paste a Google Maps link to add. Commute times fetched via TfL Journey Planner. Backfill runs automatically.
- **Weighted scoring**: Combining commute times across all POIs. Independent weight sliders per POI, normalized automatically. Score badge + weight sliders always visible. Client-side recalculation without page reload. Min-max normalization to 0-100.
- **Label overrides**: Feature pills (dishwasher/washer/outdoor) clickable on detail page, cycling yes->no->unknown->revert. Stored as nullable columns in user_state. `model_fields_set` distinguishes "not sent" from "sent as null".
- **Cross-source dedup**: Scraper normalizes addresses (strip punctuation, remove "London", collapse whitespace) and fingerprints on (address, price, bedrooms).
- **Exclude filters**: Both scrapers exclude "shared", "bedsit", "studio", "flat share", "house share", "room available".
- **Map view**: Leaflet map with colour-coded pins (gold=favourite, grey=seen, red=unseen). Popups show image preview, price, address, links.
- **Sqft display**: Stored as sqft in DB, displayed as m² (converted at render time in templates).

## UI Stack
- CSS: `ui/static/v2.css` -- warm cream bg (#f7f5f2), teal accent (#0f766e), dark mode support
- JS: `ui/static/v2.js` -- state management, filters, weight sliders, pill cycling
- Fonts: Google Fonts (Bricolage Grotesque display, DM Sans body)
- Templates: `ui/templates/` (base.html, feed.html, detail.html, map.html, settings.html)
- Data helpers: `_get_feed_data()` and `_get_detail_data()` in main.py avoid route duplication

## Gotchas
- **Outdoor detection**: Uses regex word boundaries + exclusion patterns. "communal garden", "shared garden", street names like "Gardens", and substrings ("occupation" matching "patio") are excluded.
- **Docker build context**: docker-compose.yml is in this repo. Changes must be on master branch for rebuild to pick them up.
- **DB migration**: `init_db()` creates pois/poi_commutes tables and migrates legacy commute_mins/gym_commute_mins into them. `_init_user_state_table()` runs ALTER TABLE wrapped in try/except. Both containers call on startup -- safe with WAL mode.
- **TfL rate limiting**: Backfill loops need `time.sleep(0.5)` between API calls. Without throttling, TfL returns 429 after ~50 requests.
- **TfL commute includes walking**: Journey Planner returns total door-to-door time including walk to/from stations.
