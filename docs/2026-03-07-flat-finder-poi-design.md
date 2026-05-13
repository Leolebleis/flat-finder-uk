# Dynamic Places of Interest (POI) Design

**Date:** 2026-03-07
**Project:** flat-finder

## Summary

Replace hardcoded work/gym commute destinations with user-configurable Places of Interest (POIs) managed through a settings page. Each POI has a name and coordinates (extracted from a Google Maps link). Commute times are fetched via TfL Journey Planner for all listings, with independent weight sliders for scoring.

## Data Model

### New tables

**`pois`**

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| name | TEXT NOT NULL | Display name, e.g. "Office", "Gym" |
| lat | REAL NOT NULL | Extracted from Google Maps link |
| lng | REAL NOT NULL | Extracted from Google Maps link |
| color_index | INTEGER NOT NULL | Index into fixed palette (0=blue, 1=orange, 2=purple, ...) |
| created_at | TEXT NOT NULL | ISO timestamp |

**`poi_commutes`**

| Column | Type | Notes |
|--------|------|-------|
| listing_id | TEXT NOT NULL | FK to listings.id |
| poi_id | INTEGER NOT NULL | FK to pois.id |
| commute_mins | INTEGER NOT NULL | TfL journey time in minutes |
| PRIMARY KEY | (listing_id, poi_id) | Composite key |

### Migration from current schema

On startup in `init_db()`:
1. Create new tables if they don't exist
2. If `pois` is empty and `commute_mins` column exists in listings: seed two POIs (Work at 51.5074/-0.1278, Gym at 51.5200/-0.1500) with current hardcoded coordinates
3. Copy existing `commute_mins` and `gym_commute_mins` values into `poi_commutes`
4. Old columns left in place (harmless), no longer written to

## Settings Page

### Routes

**`GET /flat/settings`** -- Settings page showing:
- List of existing POIs with name, coordinates, color swatch, delete button
- Add POI form: Name (text) + Google Maps Link (text) + Submit

**`POST /flat/settings/poi`** -- Add a POI:
- Parse Google Maps link: regex for `@lat,lng` pattern; follow redirect for `goo.gl`/`maps.app.goo.gl` short links first
- Validate name not empty, coordinates extracted successfully
- Assign next available `color_index` from palette
- Insert into `pois` table
- Trigger backfill in background thread (all listings with coordinates, 0.5s delay between TfL calls)
- Redirect back to settings

**`DELETE /flat/settings/poi/{poi_id}`** -- Remove a POI:
- Delete from `pois` and cascading `poi_commutes` rows
- Redirect back to settings

### Google Maps link parsing

Two formats to handle:
1. Full URL: `https://www.google.com/maps/.../@51.5497,-0.1782,...` -- regex extract `@lat,lng`
2. Short link: `https://maps.app.goo.gl/...` -- follow HTTP redirect to get full URL, then regex

### Color palette (8 colors, cycling)

Blue, orange, purple, teal, rose, amber, emerald, slate. Wraps around if >8 POIs.

## Scraper Changes

### Per scrape run

1. Load all POIs from `pois` table (replaces hardcoded coordinates)
2. For each new listing with coordinates: fetch TfL commute for every POI, insert into `poi_commutes`, 0.5s delay between calls
3. Backfill: query listings missing commute data for any POI, fill with 0.5s delay

### `commute.py` simplification

- Remove hardcoded `WORK_LAT/LNG`, `GYM_LAT/LNG` globals
- Remove `get_commute_mins()` and `get_gym_commute_mins()` wrappers
- Keep `_tfl_journey_mins(from_lat, from_lng, to_lat, to_lng)` as single public function (rename to `tfl_journey_mins`)

## UI Changes

### Feed page

- **Weight sliders**: Generated dynamically from POIs. Each POI gets independent 0-100 slider (default 50). Labels use POI name. Weights normalized automatically (e.g., 80/40/40 becomes 50%/25%/25%).
- **Metric badges**: Per-POI badges showing "Xmin to {name}" with POI's assigned color. Replaces hardcoded "min commute" / "min to gym".
- **Match score**: Same badge, `_compute_scores()` iterates all POIs with their weights.
- **Settings link**: Gear icon or "Settings" in header, links to `/flat/settings`.

### Detail page

Same dynamic metric badges as feed cards.

### Client-side scoring (`v2.js`)

- `recalcScores()` handles N weights instead of two
- Cards get `data-poi-{id}` attributes with commute minutes
- Slider values read from all `.poi-weight-slider` elements
- Same min-max normalization, weighted sum, N dimensions

### Notifications (ntfy)

Include commute times for all POIs in notification text: "35min to Office, 10min to Gym".

## Global defaults (not per-POI)

- Arrival time: 08:30
- Transport modes: tube, bus, overground, elizabeth-line, dlr, tram

## Non-goals

- Per-POI arrival times or transport modes
- Color picking per POI
- Map page changes
- Weight slider persistence (still reset on reload)
