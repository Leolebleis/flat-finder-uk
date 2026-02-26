# Flat Finder: Multi-Zone Search & Commute Time

## Overview

Add support for multiple search zones and show public transport commute time to a fixed destination on each listing.

## Zone Configuration

A `zones.json` file mounted into the scraper container defines all search zones:

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

Global filters (price, bedrooms, excludes) stay as env vars, shared across all zones.

**Config loading**: `ZONES_FILE` env var (default `/app/config/zones.json`). Falls back to a single-zone config from legacy env vars if file doesn't exist.

## Commute Time

The scraper calls the TfL Journey Planner API for each new listing:

```
GET https://api.tfl.gov.uk/Journey/JourneyResults/{lat},{lng}/to/51.4875,-0.1827
    ?mode=tube,bus,overground,elizabeth-line,dlr,tram
    &time=0830&timeIs=arriving
```

Destination: 38 Redcliffe Road, Chelsea (51.4875, -0.1827). Hardcoded for now.

- Free API, no key required, generous rate limits (500 req/min)
- Called once per new listing at scrape time
- Returns `duration` in minutes -- we take the shortest journey
- Stored as `commute_mins` INTEGER column on `listings` table
- Listings without coordinates get `commute_mins = NULL`

## DB Changes

Two new columns on `listings`:
- `zone TEXT` -- which zone the listing was found in
- `commute_mins INTEGER` -- public transport minutes to Redcliffe Road

Added via `ALTER TABLE` migration in `init_db()`.

## Scraper Flow (Updated)

1. Load `zones.json`
2. For each zone:
   a. Scrape Rightmove (using zone's `rightmove_id` and `radius_miles`)
   b. Scrape OpenRent (using zone's `openrent_term` and `radius_miles`)
   c. Tag each listing with `zone = zone["name"]`
3. Dedup across zones by listing ID (first zone wins)
4. Insert new listings into local DB
5. For each new listing with coordinates: call TfL API, store `commute_mins`
6. Push all listings to VPS API
7. Send notifications for new listings

## API Changes

None required. `POST /listings` already accepts arbitrary dict fields. `GET /listings` returns `SELECT *` so new columns flow through automatically.

## UI Changes

### Feed page
- **Zone filter buttons** after All/Unseen/Favourites (e.g. "All Zones | Finchley Road | St John's Wood")
- **Commute badge** on each card: "32 min" next to the distance badge
- **New sort option**: "Commute (shortest)" in the sort dropdown
- Zone filter is a query param (`?zone=Finchley+Road`) alongside the existing `?sort=` param

### Map page
- No change needed. All pins show regardless of zone.

### Detail page
- Show commute time in the metadata section.

## Config Changes

### Removed env vars
- `RIGHTMOVE_LOCATION_ID` -- moved to zones.json
- `SEARCH_RADIUS_MILES` -- moved to zones.json

### New env var
- `ZONES_FILE` -- path to zones.json (default `/app/config/zones.json`)

### Kept as global env vars
- `MAX_RENT_PCM`, `MIN_BEDROOMS`, `MAX_BEDROOMS` -- shared across all zones

### Docker volume mount
```yaml
flat-finder-scraper:
  volumes:
    - ./config/flat-finder/zones.json:/app/config/zones.json:ro
```

## Key Decisions

- **Zone overlap**: If a listing appears in multiple zones, it gets the first zone's name. No duplicates.
- **Commute destination hardcoded**: 38 Redcliffe Road. Making it configurable is easy later but YAGNI.
- **TfL query time**: 8:30am arriving, gives realistic morning commute estimate.
- **Backward compatibility**: If `zones.json` doesn't exist, fall back to single zone from `RIGHTMOVE_LOCATION_ID` / `SEARCH_RADIUS_MILES` env vars.
