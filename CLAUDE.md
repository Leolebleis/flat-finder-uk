# Flat Finder

Property alert system. Scrapes Rightmove + OpenRent, displays listings in a local web UI.

Design docs: `docs/2026-03-07-flat-finder-poi-design.md`, `docs/2026-03-07-drawable-zones-design.md`, `docs/2026-02-26-flat-finder-multi-zone-plan.md`, `docs/flat-finder-deployment.md`

## Structure
- Everything runs on Pi as Docker containers via its own `docker-compose.yml` (separate from mediastack)
- `scraper/` and `ui/` share the same SQLite DB via `flat-finder-data` volume (WAL mode)
- `shared/` (models, config, geo) used by both components
- Attached to the external `pi-net` Docker network (defined by the raspberrypi meta-repo's compose) so nginx can reach the UI container
- Zones live in the `zones` table (drawable via Settings page); `zones.json` no longer mounted

## Components
- **scraper/** -- Rightmove + OpenRent scrapers, iterates zones, fetches TfL commute times for all POIs for new listings. Cross-source dedup by address+price+bedrooms. Runs every 15 min.
- **ui/** -- FastAPI + Jinja2. Redesigned "Warm Minimal" UI (Bricolage Grotesque + DM Sans, teal accent). Feed with zone filter, weighted scoring, seen/favourite/notes, label overrides. Dark mode via prefers-color-scheme.
- **shared/models.py** -- SQLite schema (listings, pois, poi_commutes), migrations, insert/query helpers
- **shared/config.py** -- env var config (DB_PATH, NTFY_TOPIC, rent/bedroom bounds)
- **shared/geo.py** -- Google Maps URL parser (extracts lat/lng from full URLs and short links)
- **shared/zones.py** -- Polygon utilities (centroid, point-in-zone) + external lookups (postcodes.io, Rightmove LOS typeahead)
- **shared/scraping.py** -- Shared scraper helpers: EXCLUDE_TERMS, should_exclude_text, check_description, HTTP_HEADERS (pre-compiled appliance/outdoor regexes)

## Tooling
- Dep manager: `uv` (single `pyproject.toml` + `uv.lock` at repo root)
- Python: 3.13 (pinned in `.python-version`)
- PR workflow: branch off `main` (`chore/`, `feat/`, `style/`, `fix/`); do **not** commit directly to `main` for non-trivial changes. Open PRs with `gh pr create`.
- Lint/format: `ruff` (config in `pyproject.toml`, `select=ALL` with `D/COM812/ISC001` ignored)
- Type check: `ty` (Astral)
- Tests: `pytest` + `pytest-cov` + `pytest-asyncio`
- CI: GitHub Actions (`.github/workflows/ci.yml`) -- lint, type-check, test on push/PR to main
- Both Dockerfiles use a uv multi-stage build; the project is installed as a wheel containing `shared/`, `scraper/`, `ui/` (including templates/static)

## Key commands
- Install/sync deps: `uv sync`
- Run tests: `uv run pytest -v`
- Lint: `uv run ruff check .` / `uv run ruff format .`
- Type check: `uv run ty check shared/ scraper/ ui/`
- Rebuild containers: `docker compose up -d --build` (from this directory)
- Scraper logs: `docker logs flat-finder-scraper`
- UI logs: `docker logs flat-finder`
- UI URL: https://raspberrypi/flat/

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
- **Tests + Windows tempfile**: `tempfile.NamedTemporaryFile(suffix=".db")` fails on Windows (file held open exclusively, sqlite can't open it) -- ~50 tests fail locally on Windows, all pass on Linux/CI. Don't chase these failures.
- **`cursor.lastrowid` narrowing**: Typed `int | None` per stubs but always set after INSERT. Narrow with `if x is None: raise RuntimeError(msg)` -- NOT `assert` (ruff S101 bans asserts in source; allowed in tests).
- **bs4 attribute access**: `tag["attr"]` / `tag.get("attr")` returns `str | AttributeValueList | None`. Guard with `isinstance(value, str)` before string ops or ty fails.
- **Hatch wheel inclusion**: `packages = ["ui"]` already includes non-Python files (templates/, static/, binaries) under that dir. Don't add `force-include` -- it duplicates entries and warns at build time.
- **Outdoor detection**: Uses regex word boundaries + exclusion patterns. "communal garden", "shared garden", street names like "Gardens", and substrings ("occupation" matching "patio") are excluded.
- **Docker build context**: docker-compose.yml is in this repo. Changes must be on `main` for the Pi-side rebuild to pick them up.
- **DB schema ownership**: All schemas live in `shared/models.py::init_db` (listings, scraper_state, pois, poi_commutes, zones, user_state). Both scraper + UI containers call `init_db` on startup -- safe with WAL. Do NOT declare schemas in `ui/` or `scraper/`; the scraper writes to UI-owned tables (e.g. prune-orphan cleanup) and that only works because `init_db` is shared.
- **Column migrations**: Use `_ensure_columns(conn, table, [(col, type)])` (PRAGMA table_info guard). Avoid `try/except sqlite3.OperationalError: pass` — it runs the ALTER on every startup.
- **TfL rate limiting**: Backfill loops need `time.sleep(0.5)` between API calls. Without throttling, TfL returns 429 after ~50 requests.
- **TfL commute includes walking**: Journey Planner returns total door-to-door time including walk to/from stations.
