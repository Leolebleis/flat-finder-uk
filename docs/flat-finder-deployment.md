# Flat Finder Deployment

**Status**: Deployed and running on Pi. GitHub: https://github.com/Leolebleis/flat-finder (private).

## Architecture (Pi-only)

Everything runs on Pi as Docker containers via its own `docker-compose.yml` (separate from mediastack). No VPS involvement.

### Containers
- **flat-finder** (UI): uvicorn on port 8000, FastAPI + Jinja2. Nginx (mediastack) proxies `/flat/` to it via external `flat-finder-net` Docker network.
- **flat-finder-scraper**: 15min sleep loop, scrapes Rightmove + OpenRent across configured zones, fetches TfL commute times (work + gym) for new listings.

### Networking
- External Docker network `flat-finder-net` bridges mediastack's nginx to flat-finder UI
- Both nginx (mediastack) and flat-finder join this network
- Scraper has no inbound connections, only needs outbound internet

### Shared State
- Both containers mount `flat-finder-data:/app/data` volume
- Same SQLite DB: `/app/data/flat_finder.db` (WAL mode for concurrent access)
- Zone config: `/opt/mediastack/config/flat-finder/zones.json` mounted read-only into scraper
- Env vars (NTFY_TOPIC, GMAIL_*) in `.env` (gitignored)

### Features
- Multi-zone search (Finchley Road + St John's Wood, configurable via zones.json)
- TfL commute time to work (38 Redcliffe Road SW10, arriving 0830)
- TfL commute time to gym (Anytime Fitness Swiss Cottage)
- Weighted "Best match" scoring with client-side weight sliders (commute vs gym), always visible
- Redesigned UI: Bricolage Grotesque + DM Sans fonts, warm cream/teal palette, dark mode
- Label overrides: clickable feature pills cycle yes/no/unknown/revert, stored in user_state
- Cross-source deduplication by normalized address + price + bedrooms
- Room listing exclusion (flat share, house share, room available)
- Zone filter buttons, commute sort
- Seen/favourite/notes per listing (user_state table)
- Dark mode (prefers-color-scheme)
- ntfy + Gmail notifications for new listings (tapping ntfy opens listing URL)
- Listing date shown on cards (first_seen, DD/MM/YYYY format)
- Sqft displayed as m² (converted at render time)
- Map view with image previews in popups

### VPS Cleanup (TODO)
The VPS still has stale flat-finder artifacts that could be cleaned up:
- `/home/dev/projects/flat-finder/` -- old code checkout
- `flat-finder-api.service` -- disabled systemd service
- nginx `/flat/api/` location block
These are inactive and harmless but could be removed.
