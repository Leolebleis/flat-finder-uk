# Flat Finder

Property alert system. Design: `../../docs/plans/2026-02-26-flat-finder-design.md`

## Structure
- `scraper/` + `api/` run on VPS (`/home/dev/projects/flat-finder/`)
- `ui/` runs on Pi as Docker container in mediastack
- `shared/` used by all components

## Pi context
See `../../raspberrypi/CLAUDE.md` and `../../raspberrypi/docs/pi-mediastack.md`

## Key commands
- VPS: `ssh -i ~/.ssh/id_ed25519 -p 24420 dev@disqt.com`
- Run scraper manually: `cd /home/dev/projects/flat-finder && python -m scraper.scraper`
- Run API locally: `cd /home/dev/projects/flat-finder && uvicorn api.main:app --port 8090`
