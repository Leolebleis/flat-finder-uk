# Drawable Zones Design

**Date:** 2026-03-07
**Status:** Approved

## Overview

Replace the static `zones.json` config file with user-drawn polygon zones managed via the Settings UI. Users draw irregular shapes on a map (like Rightmove/Zoopla's "draw a search"), and the scraper uses those polygons to post-filter results from circular API searches.

## Why Polygons + Post-Filtering

Rightmove and OpenRent only support center-point + radius searches. Neither accepts polygon/coordinate queries. The approach:

1. User draws a polygon on the map
2. System computes a covering circle (centroid + smallest enclosing radius)
3. Scraper queries Rightmove/OpenRent using that circle
4. Results with coordinates outside the polygon are discarded

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Drawing UI | Leaflet-Geoman free (CDN) | Actively maintained, MIT, replaces dead Leaflet.draw. Outputs GeoJSON via `layer.toGeoJSON()` |
| Storage | GeoJSON Geometry as TEXT in SQLite | Native format for both Leaflet and Shapely -- zero conversion |
| Python geometry | Shapely 2.x (~3MB, pre-built arm64 wheel) | `polygon.contains(point)`, `.centroid`, `.minimum_bounding_circle()` |
| Spatial DB extensions | None (skip SpatiaLite) | With ~5-20 zones, Python-side geometry is instant. Not worth 50MB Docker bloat |
| Reverse geocoding | postcodes.io (free, no auth, UK-only) | Centroid -> postcode for search term resolution |
| Rightmove ID lookup | `los.rightmove.co.uk/typeahead` (free, no auth) | Postcode -> `OUTCODE^N` location identifier |

## Data Model

New `zones` table in SQLite:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `name` | TEXT NOT NULL | Display name |
| `geometry` | TEXT NOT NULL | GeoJSON Geometry object: `{"type": "Polygon", "coordinates": [[[lng,lat], ...]]}` |
| `centroid_lat` | REAL NOT NULL | Computed centroid latitude |
| `centroid_lng` | REAL NOT NULL | Computed centroid longitude |
| `covering_radius_km` | REAL NOT NULL | Smallest circle from centroid enclosing the polygon |
| `rightmove_id` | TEXT | Auto-resolved via LOS typeahead (e.g. `OUTCODE^1862`) |
| `openrent_term` | TEXT | Postcode/area name for OpenRent search |
| `color_index` | INTEGER NOT NULL | Reuses 8-color POI palette |
| `created_at` | TEXT NOT NULL | ISO timestamp |

The existing `listings.zone` column continues to store zone name as text.

## Scraper Changes

1. `load_zones()` reads from `zones` table instead of `zones.json`
2. For each zone, builds covering circle search:
   - Rightmove: stored `rightmove_id` + `covering_radius_km` (converted to miles)
   - OpenRent: stored `openrent_term` + `covering_radius_km`
3. Fetches listings as before
4. Post-filter: `polygon.contains(Point(lng, lat))` -- drops listings outside the drawn shape
5. Listings without coordinates kept and tagged with zone name
6. Fix OpenRent radius bug: `within` param is km, not miles

## Zone Resolution (at creation time)

When a zone polygon is saved:

1. Compute centroid via Shapely
2. Compute covering radius via `minimum_bounding_circle()`
3. Reverse-geocode centroid to postcode via `api.postcodes.io/postcodes?lon=X&lat=Y`
4. Resolve Rightmove ID via `los.rightmove.co.uk/typeahead?query={outcode}`
5. Store `openrent_term` as the postcode outcode (e.g. "NW6")

All stored in DB so lookups happen once, not every scrape cycle.

## Settings UI -- Zone Management

Added to the existing Settings page, below the POI section.

**Zone list** -- each zone shows:
- Color swatch + name
- Small inline map preview showing polygon shape
- Vertex count
- Auto-resolved search info (e.g. "NW6 -- OUTCODE^1862")
- Delete button

**Add Zone flow:**
1. Click "Add Zone" -- expands full-width map panel with Leaflet-Geoman drawing enabled
2. Draw polygon (click vertices, close by clicking first vertex)
3. Enter zone name
4. Click "Save" -- POST to API with name + GeoJSON geometry
5. Backend resolves search parameters automatically
6. Zone appears in list, map panel collapses

**Edit flow:**
Click a zone to re-open map panel with polygon editable (Geoman edit mode -- drag vertices, add/remove). Save re-resolves search parameters if shape changed.

## Map View -- Zone Overlays

The listings map (`/flat/map`) gets read-only zone polygon overlays:

- Semi-transparent filled polygons using zone's assigned color (8-color palette)
- Borders slightly darker/more opaque than fill
- Zone name label at centroid
- Polygons render behind listing pins
- Toggle checkbox to show/hide overlays (defaults visible)
- No editing on map page -- editing stays on Settings

## Migration

On first `init_db()` with new `zones` table:

1. Check if `zones` table is empty
2. If empty AND `zones.json` exists, read it
3. For each zone in JSON:
   - Generate 32-vertex circular polygon from `lat/lng` + `radius_miles`
   - Store `rightmove_id` and `openrent_term` from JSON directly
   - Compute centroid + covering radius via Shapely
4. After migration, `zones.json` mount can be removed from `docker-compose.yml`

Both containers (UI + scraper) need Shapely in `requirements.txt`.

## External APIs

| API | When Called | Rate Limits |
|-----|-----------|-------------|
| `api.postcodes.io` | Zone creation/edit | Free, no auth, generous limits |
| `los.rightmove.co.uk/typeahead` | Zone creation/edit | Free, no auth |
| Rightmove search | Every scrape cycle | Existing -- no change |
| OpenRent search | Every scrape cycle | Existing -- no change |

## Effort Estimate

| Area | Size |
|------|------|
| DB schema + migration | Small |
| Scraper changes (zone source, post-filter, radius fix) | Medium |
| Settings UI (drawing, zone CRUD, map panel) | Large |
| Map overlays | Small |
| External API calls (postcodes.io, LOS) | Small |
