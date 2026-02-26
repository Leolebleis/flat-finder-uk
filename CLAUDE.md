# Flat Finder

Property alert system. Design: `../../docs/plans/2026-02-26-flat-finder-design.md`

## Structure
- Everything runs on Pi as Docker containers in mediastack
- `scraper/` and `ui/` share the same SQLite DB via `flat-finder-data` volume
- `shared/` used by both components
- Zone config loaded from `/opt/mediastack/config/flat-finder/zones.json`

## Pi context
See `../../raspberrypi/CLAUDE.md` and `../../raspberrypi/docs/pi-mediastack.md`

## Key commands
- Rebuild: `cd /opt/mediastack && docker compose up -d --build flat-finder flat-finder-scraper`
- Scraper logs: `docker logs flat-finder-scraper`
- UI logs: `docker logs flat-finder`
- UI URL: https://raspberrypi/flat/
