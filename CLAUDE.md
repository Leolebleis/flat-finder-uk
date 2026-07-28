# Flat Finder

Property alert system. Scrapes Rightmove + OpenRent, displays listings in a local web UI.

Design docs: `docs/2026-03-07-flat-finder-poi-design.md`, `docs/2026-03-07-drawable-zones-design.md`, `docs/2026-02-26-flat-finder-multi-zone-plan.md`

## Structure
- Single `flat_finder/` package, domain-first (clean architecture). UI and scraper are two container targets off the same package.
- Runs as Docker containers via `docker-compose.yml`; both share the same SQLite DB via `flat-finder-data` volume (WAL mode)
- Domain folders (`listings/`, `pois/`, `zones/`, `users/`) each hold `model.py` (domain entity), `dao.py` (abstract protocol), `service.py` (business logic), and `persistence.py` (ORM + repository implementing the dao)
- Architecture enforced by import-linter (`lint-imports`): domain models must not import infrastructure
- Multi-user: per-user zones, POIs, user_state (seen/favourite/notes), ntfy topic, and search params. Auth via signed session cookie (`flat_finder/users/auth.py`).

## Components
- **flat_finder/scraper/** -- `runner.py` (orchestrates: Rightmove + OpenRent scrapers, iterates zones, populates listing_zones, per-user ntfy, archive), `commute.py` (CommuteClient protocol), `transitous.py` (UK-wide commute client), `notifier.py`. Runs every 15 min (`while true; sleep 900` in container CMD).
- **flat_finder/api/** -- FastAPI app. `app.py` (create_app factory, root_path=`/flat`, middleware), `dependencies.py` (DI via Depends), one module per page/route group (`feed.py`, `detail.py`, `settings.py`, `map_page.py`, `auth_routes.py`, `*_api.py`).
- **flat_finder/database.py** -- SQLAlchemy engine (WAL + busy_timeout), session factory. **persistence.py** -- imports all model modules to register the shared `Base`.
- **flat_finder/config.py** -- env var config (DB_PATH, SECRET_KEY, rent/bedroom bounds). DB_PATH evaluated at import time.
- **flat_finder/geo.py** -- Google Maps URL parser (extracts lat/lng from full URLs and short links)
- **flat_finder/zone_utils.py** -- Polygon utilities (centroid, point-in-zone) + external lookups (postcodes.io, Rightmove LOS typeahead)
- **flat_finder/scraping.py** -- Shared scraper helpers: EXCLUDE_TERMS, should_exclude_text, check_description, HTTP_HEADERS (pre-compiled appliance/outdoor regexes)

## Tooling
- Dep manager: `uv` (single `pyproject.toml` + `uv.lock` at repo root)
- Python: 3.13 (pinned in `.python-version`)
- PR workflow: branch off `main` (`chore/`, `feat/`, `style/`, `fix/`); do **not** commit directly to `main` for non-trivial changes. Open PRs with `gh pr create`.
- Lint/format: `ruff` (config in `pyproject.toml`, `select=ALL` with `D/COM812/ISC001` ignored)
- Type check: `ty` (Astral)
- Tests: `pytest` + `pytest-cov` + `pytest-asyncio`
- CI: GitHub Actions (`.github/workflows/ci.yml`) -- 5 jobs: lint, type-check, architecture (import-linter), test, e2e (Playwright) on push/PR to main
- Single multi-stage `Dockerfile` with `ui` and `scraper` targets (uv build); the project is installed as a wheel containing `flat_finder/` (including templates/static). Containers run `alembic upgrade head` before starting.

## Environment
- `SECRET_KEY` -- **required** for session auth; insecure default (`dev-secret-change-in-production`) if unset. On the Pi, set in `.env` (gitignored). Generate: `python -c "import secrets; print(secrets.token_hex(32))"`.
- `FLAT_FINDER_DB` -- SQLite path (default `/app/data/flat_finder.db`). Evaluated at import time.
- `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` -- optional, for email notifications.
- `SCRAPLING_MCP_URL` -- optional; routes Rightmove fetches through a scrapling MCP container (Chrome TLS fingerprint, avoids WAF bot-checks). On the Pi set to `http://gluetun:8001/mcp` in `.env` (scraper is on pi-net). Empty = direct fetches. Never route OpenRent through it: its AWS WAF blocks VPN/datacenter IPs.
- `SCRAPER_REALERT_HOURS` -- optional; how often to re-notify about a source that is still failing (default 24, `0` disables). Failure alerts are otherwise edge-triggered, so a permanently broken source would alert once and then look identical to a healthy one.
- `COMMUTE_PRENOTIFY_CALLS` -- optional; commute API requests spent enriching new listings before notifications are sent (default 40, `0` sends with no commute times). Budgeted in requests, not listings, because the cost is one request per distinct coordinate **per POI** — the budget is divided across POIs. The remainder is backfilled after the pushes go out.
- Rent/bedroom env vars are scraper fallbacks; per-user search params (set in Settings) take precedence.

## Key commands
- Install/sync deps: `uv sync`
- Run unit/integration tests: `uv run pytest --ignore=tests/e2e -v`
- Run E2E tests (needs browsers once): `uv run playwright install chromium` then `uv run pytest tests/e2e/ -v`
- Lint: `uv run ruff check .` AND `uv run ruff format --check .` — CI runs both; `ruff check` passing does NOT mean format passes. Run `uv run ruff format .` to fix.
- Type check: `uv run ty check flat_finder/`
- Rebuild containers: `docker compose up -d --build` (from this directory)
- Scraper logs: `docker logs flat-finder-scraper`
- UI logs: `docker logs flat-finder`

## Features
- **Dynamic POIs**: User-configurable Places of Interest via Settings page. Paste a Google Maps link to add. Commute times fetched via Transitous API (UK-wide public transit, replaces TfL which only covered London). Backfill runs automatically.
- **Weighted scoring**: Combining commute times across all POIs. Independent weight sliders per POI, normalized automatically. Score badge + weight sliders always visible. Client-side recalculation without page reload. Min-max normalization to 0-100.
- **Label overrides**: Feature pills (dishwasher/washer/outdoor) clickable on detail page, cycling yes->no->unknown->revert. Stored as nullable columns in user_state. `model_fields_set` distinguishes "not sent" from "sent as null".
- **Cross-source dedup**: Scraper normalizes addresses (strip punctuation, remove "London", collapse whitespace) and fingerprints on (address, price, bedrooms).
- **Exclude filters**: Both scrapers exclude "shared", "bedsit", "studio", "flat share", "house share", "room available".
- **Map view**: Leaflet map with colour-coded pins (gold=favourite, grey=seen, red=unseen). Popups show image preview, price, address, links.
- **Sqft display**: Stored as sqft in DB, displayed as m² (converted at render time in templates).

## UI Stack
- CSS: `flat_finder/static/v2.css` -- blue accent (#2563eb), warm neutrals, dark mode support
- JS: `flat_finder/static/v2.js` -- state management, filters, weight sliders, pill cycling
- Fonts: Google Fonts (Space Grotesk display, Outfit body)
- Templates: `flat_finder/templates/` (base.html, feed.html, detail.html, map.html, settings.html, login.html)
- Routes live in `flat_finder/api/*.py` (one module per page/route group), not a single main.py. Shared data-shaping helpers sit alongside their routes.

## Gotchas
- **Tests + Windows tempfile**: `tempfile.NamedTemporaryFile(suffix=".db")` fails on Windows (file held open exclusively, sqlite can't open it) -- ~50 tests fail locally on Windows, all pass on Linux/CI. Don't chase these failures.
- **`cursor.lastrowid` narrowing**: Typed `int | None` per stubs but always set after INSERT. Narrow with `if x is None: raise RuntimeError(msg)` -- NOT `assert` (ruff S101 bans asserts in source; allowed in tests).
- **bs4 attribute access**: `tag["attr"]` / `tag.get("attr")` returns `str | AttributeValueList | None`. Guard with `isinstance(value, str)` before string ops or ty fails.
- **Hatch wheel inclusion**: `packages = ["flat_finder"]` already includes non-Python files (templates/, static/, binaries) under that dir. Don't add `force-include` -- it duplicates entries and warns at build time.
- **Outdoor detection**: Uses regex word boundaries + exclusion patterns. "communal garden", "shared garden", street names like "Gardens", and substrings ("occupation" matching "patio") are excluded.
- **Docker build context**: docker-compose.yml is in this repo. Changes must be on `main` for rebuild to pick them up.
- **Merging is not deploying**: containers only get new code after `git pull` + `docker compose up -d --build` on the Pi. When something is "still broken", first compare `docker ps --format '{{.Names}} {{.CreatedAt}}'` against the fix's merge date.
- **Rebuild discards logs**: `docker compose up -d --build` recreates containers and their logs are lost. Capture `docker logs flat-finder-scraper` to a file before rebuilding when debugging.
- **DB schema ownership**: Each domain folder owns its ORM models in `<domain>/persistence.py`, all registered on a shared SQLAlchemy `Base` (see `flat_finder/persistence.py`, which imports every model module). Schema changes go through Alembic migrations in `alembic/versions/`; containers run `alembic upgrade head` on startup (safe with WAL). The scraper writes to UI-owned tables (e.g. prune-orphan, listing_zones) -- that works because all models share one `Base.metadata`.
- **Migrations**: Use Alembic (`alembic revision --autogenerate -m "..."` then review). SQLite needs batch mode for column drops/alters. Migrations must handle both fresh and existing DBs (the Pi has live data).
- **Commute API rate limiting**: Backfill loops need `time.sleep(0.5)` between API calls. Transitous is community-run — be respectful of their resources.
- **Commute times include walking**: Transitous returns total door-to-door time including walk to/from stations.
- **CommuteClient protocol**: `flat_finder/scraper/commute.py` defines a `CommuteClient` protocol. `TransitousCommuteClient` is the concrete implementation. Swap providers by implementing the protocol.
- **Swapping commute providers**: `get_listings_missing_poi` excludes any listing that already has a `poi_commutes` row — including `NO_JOURNEY` (-1) sentinels. After changing providers, clear stale sentinels (`DELETE FROM poi_commutes WHERE commute_mins < 0`) or previously-unroutable listings never get retried.
- **Inspecting the live Pi DB**: `docker exec flat-finder-scraper python -c "import sqlite3; ..."` against `/app/data/flat_finder.db` (no `sqlite3` CLI in the slim image).
