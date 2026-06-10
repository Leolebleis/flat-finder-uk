# Flat Finder UK

Property alert system for UK renters. Scrapes Rightmove and OpenRent on a schedule, scores each listing against your commute priorities, and serves everything through a local, multi-user web UI.

## What it does

- **Multi-user**: log in with a username (no password); each user gets their own zones, places of interest, search criteria, notifications, and seen/favourite/notes state
- **Scrapes two sources** every 15 minutes: Rightmove (JSON API) and OpenRent (HTML parsing)
- **Deduplicates** across sources by normalised address + price + bedrooms
- **Fetches commute times** from [Transitous](https://transitous.org) (community-run, UK-wide public transit) for each listing and each Place of Interest you configure
- **Scores listings** with adjustable per-POI weight sliders (client-side, no page reload)
- **Filters** by search zone, seen/unseen/favourites, and sort order
- **Tracks your state**: mark seen, favourite, add notes, override detected features (dishwasher, washer, outdoor space)
- **Map view** with colour-coded pins and zone overlays
- **Dark mode** via `prefers-color-scheme`
- **Push notifications** via [ntfy.sh](https://ntfy.sh) — one per new listing, to a per-user topic

## Architecture

A single domain-first `flat_finder/` package (clean architecture); the UI and scraper are two container targets built from it.

```
flat_finder/
  api/          FastAPI app — routers, auth middleware, dependency wiring
  scraper/      Rightmove + OpenRent scrapers, Transitous commute client, ntfy notifier
  listings/     \
  pois/          )  domain folders, each: model (entity) + dao (protocol)
  zones/         )  + service (logic) + persistence (SQLAlchemy ORM + repo)
  users/        /   (users/ also holds login + auth)
  templates/    Jinja2 pages (feed, detail, map, settings, login)
  static/       CSS / JS / Leaflet assets
alembic/        database migrations (run on container startup)
```

Both containers share a single SQLite database (WAL mode) through a Docker volume — no external database required. Architecture boundaries are enforced in CI by [import-linter](https://github.com/seddonym/import-linter): domain models cannot import infrastructure.

## Quick start

### Prerequisites

- Docker and Docker Compose
- A network where the UI container is reachable (or an nginx reverse proxy)

### 1. Clone and configure

```bash
git clone https://github.com/Leolebleis/flat-finder-uk.git
cd flat-finder-uk
cp .env.example .env
```

Edit `.env` and set a `SECRET_KEY` (required — it signs the login session cookie):

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Start

```bash
docker compose up -d --build
```

The UI listens on port 8000 inside the container. The compose file attaches it to a Docker network for an nginx reverse proxy (mount the location at `/flat/`); to reach it directly instead, publish the port by adding `ports: ["8000:8000"]` to the `flat-finder` service.

Alembic migrations run automatically on startup.

### 3. Log in

Open the UI and enter a username. The account is created on first login and cached in your browser via a signed cookie. Each user's data is fully independent.

### 4. Add search zones

On the Settings page, click **Add Zone** and draw a polygon on the map. The scraper resolves your polygon to Rightmove and OpenRent search parameters automatically and filters results to inside your zones.

### 5. Add Places of Interest

Paste a Google Maps link for each destination you care about (office, gym, partner's flat). The scraper fetches Transitous commute times for every listing, and the feed scores listings by weighted travel time across all your POIs.

### 6. Set your search criteria and notifications

On the Settings page, set your max rent and bedroom range (per user), and copy your auto-generated ntfy topic to subscribe for push notifications.

## Configuration

Configuration is through environment variables; see `.env.example`. Search criteria and notification topics are configured **per user in the UI**, not via env vars.

| Variable | Default | Purpose |
|----------|---------|---------|
| `SECRET_KEY` | `dev-secret-change-in-production` | **Required.** Signs the login session cookie. Set to a random 32-byte hex string. |
| `FLAT_FINDER_DB` | `/app/data/flat_finder.db` | SQLite database path (both containers) |
| `GMAIL_ADDRESS` | | Gmail address for optional email notifications |
| `GMAIL_APP_PASSWORD` | | Gmail app password |

## Development

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                   # Install dependencies
uv run pytest --ignore=tests/e2e -v       # Unit + integration tests
uv run playwright install chromium        # One-time: E2E browser
uv run pytest tests/e2e/ -v               # End-to-end browser tests
uv run ruff check . && uv run ruff format --check .   # Lint + format (CI runs both)
uv run ty check flat_finder/              # Type check
uv run lint-imports                       # Architecture boundaries
```

CI (GitHub Actions) runs five jobs on every push: lint, type-check, architecture, test, and e2e.

## Tech stack

- **Backend**: FastAPI, Jinja2, SQLAlchemy + Alembic, SQLite (WAL mode)
- **Frontend**: Vanilla JS, CSS custom properties, Leaflet maps
- **Scraping**: BeautifulSoup, Requests
- **Commute**: [Transitous](https://transitous.org) API (free, UK-wide, no key required)
- **Auth**: signed session cookies (Starlette `SessionMiddleware`)
- **Deployment**: Docker multi-stage builds with uv
- **Notifications**: ntfy.sh, Gmail SMTP

## License

MIT
