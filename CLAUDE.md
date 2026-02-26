# Flat Finder

Property alert system. Scrapes Rightmove + OpenRent, displays listings in a local web UI.

Design docs: `../../docs/plans/2026-02-26-flat-finder-design.md`, `../../docs/plans/2026-02-26-flat-finder-scoring-design.md`

## Structure
- Everything runs on Pi as Docker containers in mediastack
- `scraper/` and `ui/` share the same SQLite DB via `flat-finder-data` volume (WAL mode)
- `shared/` (models, config) used by both components
- Zone config: `/opt/mediastack/config/flat-finder/zones.json` (mounted read-only into scraper)

## Components
- **scraper/** -- Rightmove + OpenRent scrapers, iterates zones, fetches TfL commute times for new listings. Cross-source dedup by address+price+bedrooms. Runs every 15 min.
- **ui/** -- FastAPI + Jinja2. Feed with zone filter, weighted scoring sort, seen/favourite/notes state, label overrides. Dark mode via prefers-color-scheme.
- **shared/models.py** -- SQLite schema, migrations (ALTER TABLE for new columns), insert/query helpers
- **shared/config.py** -- env var config + `load_zones()` from JSON

## Key commands
- Rebuild: `cd /opt/mediastack && docker compose up -d --build flat-finder flat-finder-scraper`
- Scraper logs: `docker logs flat-finder-scraper`
- UI logs: `docker logs flat-finder`
- UI URL: https://raspberrypi/flat/
- Run tests: `.venv/bin/python -m pytest tests/ -v`

## Key coordinates
- **Commute destination** (38 Redcliffe Road SW10): 51.4869, -0.1832 -- in `scraper/commute.py`
- **Gym** (Anytime Fitness Swiss Cottage): 51.5445, -0.1762 -- in `ui/main.py`
- **Finchley Road Station** (station distance): 51.5472, -0.1803 -- in `ui/main.py`

## Features
- **Weighted scoring**: "Best match" sort combining commute time + gym proximity. Client-side weight sliders recalculate without page reload. Min-max normalization to 0-100.
- **Label overrides**: Feature pills (dishwasher/washer/outdoor) clickable on detail page, cycling yes->no->unknown->revert. Stored as nullable columns in user_state. `model_fields_set` distinguishes "not sent" from "sent as null".
- **Cross-source dedup**: Scraper normalizes addresses (strip punctuation, remove "London", collapse whitespace) and fingerprints on (address, price, bedrooms).
- **Exclude filters**: Both scrapers exclude "shared", "bedsit", "studio", "flat share", "house share", "room available".

## Gotchas
- **Outdoor detection**: Uses regex word boundaries + exclusion patterns. "communal garden", "shared garden", street names like "Gardens", and substrings ("occupation" matching "patio") are excluded.
- **Docker build context**: docker-compose points to this repo directory. Changes must be on master branch for rebuild to pick them up.
- **DB migration**: `init_db()` and `_init_user_state_table()` run ALTER TABLE wrapped in try/except. Both containers call on startup -- safe with WAL mode.
- **Gym distance**: Haversine (straight-line), not walking time. May want TfL walking API in future.
