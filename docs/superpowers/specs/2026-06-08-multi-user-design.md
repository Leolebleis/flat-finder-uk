# Multi-User Support + Architecture Restructure

Two combined efforts: (1) restructure the codebase toward Clean Architecture with a proper tooling stack, and (2) add multi-user support.

## New Tooling Stack

| Tool | Purpose | Replaces |
|------|---------|----------|
| SQLAlchemy 2.0 (sync) | ORM, Data Mapper pattern | Raw sqlite3 + hand-written SQL |
| Alembic (batch mode) | Schema migrations | Ad-hoc `_ensure_columns` / `CREATE TABLE IF NOT EXISTS` |
| import-linter | Architecture enforcement in CI | Nothing (new) |
| FastAPI `Depends()` | Dependency injection | Direct construction in route handlers |

No DI framework -- `Depends()` is sufficient for ~10 routes and a simple dependency graph.

## Architecture Restructure

Domain-first folder layout. Top-level folders describe what the app does, not what framework it uses.

```
flat_finder/
  listings/
    model.py              # domain entity (dataclass)
    dao.py                # abstract persistence protocol
    service.py            # business logic
    router.py             # FastAPI routes
    mapper.py             # API <-> domain mapping
    persistence/
      listing_db.py       # SQLAlchemy model + DAO implementation
      listing_mapper.py   # ORM model <-> domain entity
    model_api/
      requests.py         # Pydantic request models
      responses.py        # Pydantic response models
  zones/
    model.py
    dao.py
    service.py
    router.py
    mapper.py
    persistence/
      zone_db.py
      zone_mapper.py
  pois/
    ...same pattern...
  users/
    ...same pattern...
  scraper/
    scraper.py            # orchestration
    rightmove.py
    openrent.py
    commute.py
    notifier.py
  shared/
    config.py             # env var config
    database.py           # SQLAlchemy engine + session factory
    scraping.py           # shared scraper helpers
    geo.py                # Google Maps URL parser
    zones.py              # polygon utilities
  ui/
    templates/            # Jinja2 templates
    static/               # CSS, JS, fonts
  main.py                 # FastAPI app, middleware, route mounting
  alembic/                # Alembic migration scripts
```

Separate models per layer:
- **Domain**: frozen dataclasses (e.g. `Listing`, `Zone`, `User`)
- **Persistence**: SQLAlchemy ORM models (e.g. `ListingDB`, `ZoneDB`)
- **API**: Pydantic request/response models (e.g. `StateUpdateRequest`, `ZoneCreateRequest`)

Mappers at each boundary. No model shared across layers.

## Auth

Username-only login with no password. The app runs on a trusted network (local + Tailscale), so identity is for personalization, not security.

- **Login page**: text field for username, submit button. Served at `/login`.
- **Auto-create**: if the username doesn't exist, a new user row is created on submit.
- **Session**: username stored in a signed httponly cookie (using FastAPI/Starlette's `SessionMiddleware` with a `SECRET_KEY` env var). No expiry -- persists until explicit logout.
- **Middleware**: every route except `/login` checks for the session cookie. Missing or invalid cookie redirects to `/login`.
- **Logout**: button in the nav bar, POST to `/logout`, clears the cookie, redirects to `/login`.

## Data Model

### New tables

**users**
```sql
CREATE TABLE users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT NOT NULL UNIQUE,
    ntfy_topic TEXT,
    created_at TEXT NOT NULL
);
```

**listing_zones** (junction table, populated at scrape time)
```sql
CREATE TABLE listing_zones (
    listing_id TEXT NOT NULL,
    zone_id    INTEGER NOT NULL,
    PRIMARY KEY (listing_id, zone_id)
);
```

**listings_archive** (cold storage for expired listings)
```sql
CREATE TABLE listings_archive (
    -- same columns as listings, but zone is a plain TEXT tag (denormalized), not a FK
    -- no relational links to zones/pois/user_state -- those are ephemeral
    -- indexed for analytics: time-series on first_seen, zone grouping, geo on lat/lng
    -- append-only, never queried by the feed
);
```

Zones are ephemeral (users redraw, rename, delete them). The archive stores the zone *name* as a metadata tag, not a relational reference. When a listing is archived, its `listing_zones`, `user_state`, and `poi_commutes` rows are dropped.

### Modified tables

**zones** -- add `user_id INTEGER NOT NULL` column.

**pois** -- add `user_id INTEGER NOT NULL` column.

**user_state** -- change PK from `listing_id` alone to `(user_id, listing_id)`. Add `user_id INTEGER NOT NULL` column.

### Unchanged tables

- **listings** -- global, no user_id. The `zone` column stays as scraper metadata (which zone name found it). Only active listings (< 14 days old).
- **scraper_state** -- global.
- **poi_commutes** -- inherits user-scoping through `poi_id` FK (a POI belongs to a user, so its commutes do too). No schema change.

### Listing retention

Replace the current hard-delete prune with an archive step:
- Listings older than 14 days are moved from `listings` to `listings_archive` (INSERT-SELECT + DELETE).
- `listings` stays lean for feed queries.
- `listings_archive` is optimized for analytics: indexed on `(first_seen, zone, bedrooms, price_pcm)` and `(latitude, longitude)` for geo queries.
- Future price trend graphs query `listings_archive`: `SELECT zone, strftime('%Y-%m', first_seen), AVG(price_pcm), bedrooms FROM listings_archive GROUP BY 1, 2, 4`.
- Orphan cleanup (`user_state`, `poi_commutes`, `listing_zones`) removes rows for archived listings.

### Migration strategy

Managed by Alembic. The initial migration:

1. Create `users` table.
2. Insert a "leo" user if no users exist.
3. Add `user_id` column to `zones`, `pois`, `user_state` (batch mode for SQLite).
4. Backfill: set `user_id = 1` (leo's ID) on all existing rows where `user_id IS NULL`.
5. Create `listing_zones` table.
6. Backfill `listing_zones` from the existing `zone` column on listings: for each listing with a non-null `zone`, find the zone row with that name and insert a `(listing_id, zone_id)` row.
7. Recreate `user_state` with composite PK `(user_id, listing_id)` (batch mode handles CREATE-COPY-DROP-RENAME).
8. Create `listings_archive` table with analytics-optimized indexes.

## Scraper Changes

### Zone iteration

The scraper queries ALL zones from ALL users globally. Deduplicates zones by `(rightmove_id, openrent_term)` pair before iterating, to avoid scraping the same search twice.

### listing_zones population

When a listing is found while scraping zone X:
- If the listing is new (inserted): write `(listing_id, zone_id)` to `listing_zones`.
- If the listing already exists (dedup): still write `(listing_id, zone_id)` to `listing_zones` if that pair doesn't exist yet.

### Per-user notifications

After the scrape loop, for each user who has an `ntfy_topic` set:
1. Find new listings in at least one of that user's zones (via `listing_zones`).
2. Fetch that user's POIs for commute display in the notification.
3. Send the ntfy notification to that user's topic.

The `NTFY_TOPIC` env var is removed. Email notifications (`GMAIL_ADDRESS`/`GMAIL_APP_PASSWORD`) remain global for now.

### Listing archival

The prune step changes from DELETE to archive:
1. `INSERT INTO listings_archive SELECT * FROM listings WHERE first_seen < datetime('now', '-14 days')` -- zone column copied as a plain text tag.
2. `DELETE FROM listings WHERE first_seen < datetime('now', '-14 days')`.
3. Orphan cleanup: remove `listing_zones`, `user_state`, and `poi_commutes` rows for archived listing IDs. These are ephemeral relational data, not needed in cold storage.

## UI Changes

### Login page

New template `login.html`. Simple centered form: username text input + submit button. Styled consistent with the existing design (Space Grotesk / Outfit, blue accent, dark mode support).

### Nav bar

- Add username display (e.g. "Leo") on the right side.
- Add logout button next to the username.

### Session middleware

`SessionMiddleware` with a `SECRET_KEY` env var. A dependency function that:
- Reads `request.session["user_id"]` and `request.session["username"]`.
- If missing, redirects to `/login` (except for the `/login` route itself).
- Returns the current user for route handlers via `Depends()`.

### Feed page

- Query `listing_zones` joined with the current user's zones to get listings.
- Zone filter dropdown shows the current user's zone names.
- A listing in multiple of the same user's zones appears once.
- Sorting, scoring, and POI commutes use the current user's POIs only.

### Detail page

- `user_state` queries filter by `(user_id, listing_id)`.
- POI commutes display uses the current user's POIs.

### Map page

- Listings filtered to those in the current user's zones.
- POIs shown are the current user's POIs.

### Settings page

- POI section: shows and manages the current user's POIs only.
- Zone section: shows and manages the current user's zones only.
- New NTFY section: text input for the user's ntfy topic, with a save button. Pre-filled with current value (or empty).

### API routes

All user-scoped routes include `user_id` from the session:
- `POST /api/state/{listing_id}` -- upserts with `(user_id, listing_id)`.
- `GET /api/zones` -- returns current user's zones only.
- `POST /api/zones` -- creates zone with current user's user_id.
- `PUT /api/zones/{zone_id}` -- verifies zone belongs to current user.
- `DELETE /api/zones/{zone_id}` -- verifies zone belongs to current user.
- `GET /api/listings` -- filters by current user's zones via listing_zones.
- `DELETE /settings/poi/{poi_id}` -- verifies POI belongs to current user.
- `POST /settings/ntfy` -- updates current user's ntfy_topic.

### Zone creation backfill

When a user creates a new zone, backfill `listing_zones`: check all existing listings with lat/lng against the new zone's polygon (point-in-polygon) and insert matching rows. Background thread, same pattern as POI commute backfill.

## Docker / Config Changes

- Add `SECRET_KEY` env var to docker-compose.yml for the UI service.
- Remove `NTFY_TOPIC` env var from docker-compose.yml (now per-user in DB).
- `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` remain unchanged (global).
- Add `sqlalchemy`, `alembic` to dependencies in `pyproject.toml`.
- Add `import-linter` to dev dependencies.
- Add import-linter config to `pyproject.toml` (layer contracts).

## Testing

- Unit tests for user CRUD, scoped queries (zones/POIs/user_state filtered by user_id).
- Test that login creates a new user and sets session cookie.
- Test that logout clears the cookie.
- Test that unauthenticated requests redirect to login.
- Test that user A's zones/POIs/state are invisible to user B.
- Test listing_zones population during scraping (new listing + dedup case).
- Test per-user ntfy notifications (user with topic gets notified, user without doesn't).
- Test listing archival (move to archive, orphan cleanup).
- Test Alembic migration runs cleanly on an existing DB with data.
- import-linter contracts pass (no cross-layer imports).
