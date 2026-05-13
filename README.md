# Flat Finder UK

Property alert system for UK renters. Scrapes Rightmove and OpenRent on a schedule, scores each listing against your commute priorities, and serves everything through a local web UI.


## What it does

- **Scrapes two sources** every 15 minutes: Rightmove (JSON API) and OpenRent (HTML parsing)
- **Deduplicates** across sources by normalised address + price + bedrooms
- **Fetches commute times** from the TfL Journey Planner for each listing and each Place of Interest you configure
- **Scores listings** with adjustable per-POI weight sliders (client-side, no page reload)
- **Filters** by search zone, seen/unseen/favourites, and sort order
- **Tracks your state**: mark seen, favourite, add notes, override detected features (dishwasher, washer, outdoor space)
- **Map view** with colour-coded pins and zone overlays
- **Dark mode** via `prefers-color-scheme`
- **Push notifications** via [ntfy.sh](https://ntfy.sh) when new listings appear

## Architecture

```
scraper/          Rightmove + OpenRent scrapers, TfL commute fetcher, ntfy notifier
ui/               FastAPI + Jinja2 web UI (feed, detail, map, settings pages)
shared/           SQLite schema, config, geo utilities, zone resolution
```

Both containers share a single SQLite database (WAL mode) through a Docker volume. No external database required.

## Quick start

### Prerequisites

- Docker and Docker Compose
- A network where the UI container is reachable (or an nginx reverse proxy)

### 1. Clone and configure

```bash
git clone https://github.com/Leolebleis/flat-finder-uk.git
cd flat-finder-uk
cp .env.example .env
# Edit .env with your notification preferences (optional)
```

### 2. Start

```bash
docker compose up -d --build
```

The UI runs on port 8000. If you proxy through nginx, mount the location at `/flat/`.

### 3. Add search zones

Open the Settings page, click **Add Zone**, and draw a polygon on the map. The scraper resolves your polygon to Rightmove and OpenRent search parameters automatically.

### 4. Add Places of Interest

Paste a Google Maps link for each destination you care about (office, gym, partner's flat). The scraper fetches TfL commute times for every listing, and the feed scores listings by weighted distance across all your POIs.

## Configuration

All configuration is through environment variables. See `.env.example` for the full list.

| Variable | Default | Purpose |
|----------|---------|---------|
| `FLAT_FINDER_DB` | `/app/data/flat_finder.db` | Database path (scraper) |
| `FLAT_FINDER_UI_DB` | `/app/data/flat_finder.db` | Database path (UI) |
| `MAX_RENT_PCM` | `2200` | Maximum rent filter |
| `MIN_BEDROOMS` | `1` | Minimum bedrooms filter |
| `MAX_BEDROOMS` | `2` | Maximum bedrooms filter |
| `NTFY_TOPIC` | | ntfy.sh topic for push notifications |
| `GMAIL_ADDRESS` | | Gmail address for email notifications |
| `GMAIL_APP_PASSWORD` | | Gmail app password |

## Development

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                        # Install dependencies
uv run pytest -v               # Run tests
uv run ruff check .            # Lint
uv run ruff format .           # Format
uv run ty check shared/ scraper/ ui/  # Type check
```

CI runs lint, type check, and tests on every push via GitHub Actions.

## Tech stack

- **Backend**: FastAPI, Jinja2, SQLite (WAL mode)
- **Frontend**: Vanilla JS, CSS custom properties, Leaflet maps
- **Scraping**: BeautifulSoup, Requests
- **Commute**: TfL Journey Planner API (free, no key required)
- **Deployment**: Docker multi-stage builds with uv
- **Notifications**: ntfy.sh, Gmail SMTP

## License

MIT
