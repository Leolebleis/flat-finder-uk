# Resilient Scraping Layer — Design Spec

**Date:** 2026-06-14
**Status:** Draft for review
**Author:** brainstormed with Claude

## Goal

Make flat-finder's scraping resilient to intermittent anti-bot blocking, and add new
listing sources behind a clean, swappable seam — starting with a proper fix for the
Rightmove `503` failures and adding **Zoopla** via the FlareSolverr container the Pi
already runs. Secondarily, give Claude Code a self-hosted way to search/fetch the web
without being bot-blocked.

## Scope (locked)

1. **Resilient fetch layer** for flat-finder — a tiered `Fetcher` abstraction + per-source
   `SiteAdapter` registry, replacing bare `requests.get` in the scrapers.
2. **Rightmove**: keep, harden, and migrate to the cleaner `www.rightmove.co.uk/api/_search`
   JSON endpoint.
3. **OpenRent**: keep, move onto the shared `HttpFetcher` (no behaviour change).
4. **Zoopla**: add as a new source, fetched via the **existing FlareSolverr** container on
   the Pi's **residential IP** (empirically proven to clear Cloudflare — see Decisions).
5. **Instrumentation**: per-source success/failure + challenge-detection logging and
   Prometheus metrics, so we measure the bottleneck before scaling.
6. **Claude Code web access** (separate, follow-on subsystem): self-hosted **SearXNG** +
   an MCP for search, and a fetch path for blocked pages.

## Non-goals / explicitly rejected (with evidence)

- **No managed scraping API** (Bright Data / Apify) now — kept only as a documented
  backstop behind the seam. FlareSolverr already solves Zoopla for free.
- **No VPN / gluetun for scraping.** Empirically tested: same Zoopla URL through gluetun's
  ProtonVPN exit (`169.150.208.217`) **timed out failing the Cloudflare challenge**, while
  the residential IP returned 28 real listings. Datacenter/VPN IPs score worse with
  Cloudflare; the residential IP is the asset. gluetun stays torrent-side only.
- **No aggregators** (Gumtree, Rentola) — low quality / mostly-duplicate / room-shares we
  already exclude. They fail the quality bar OpenRent sets.
- **No official portal APIs** — none exist for consumers; all are agent-only inbound
  publishing feeds. Zoopla's public read API has been dead since ~2016.
- **No headless browser on the Pi** beyond what FlareSolverr already runs. Camoufox/Byparr
  kept as a documented heavier fallback, not built now.
- **No Scrapling dependency** now — its browser tier is redundant with FlareSolverr and its
  light tier is replaceable by `requests` + `urllib3.Retry` (zero new deps). Kept as a
  possible future swap-in.

## Key decisions & rationale

- **Tiered fetch, not one client.** Different sources need different transports: light HTTP
  for Rightmove/OpenRent, a Cloudflare-solver (FlareSolverr) for Zoopla. A `Fetcher`
  protocol makes the transport a per-source choice and a future swap (FlareSolverr → Byparr
  → managed API) a config change, not a rewrite. Mirrors the existing `CommuteClient`
  protocol pattern.
- **Zoopla via FlareSolverr on residential IP** — proven to work (28 listings, real
  addresses/prices). Run it on the **normal 15-min loop** initially and *measure* what
  fails, rather than pre-emptively throttling. Per-source frequency is a config knob so we
  can dial back if Cloudflare pushes back.
- **Retry/backoff via `urllib3.Retry`** (zero new deps): `status_forcelist=(429,500,502,503,504)`,
  `backoff_factor≈1–2`, `backoff_jitter`, `respect_retry_after_header=True` (honors 503
  `Retry-After` natively). This is the actual fix for the original Rightmove 503 bug.
- **Return partial results on mid-pagination failure** — stop discarding already-fetched
  pages when a later page fails (current `fetch_rightmove` loses the whole zone on one 503).
- **Coherent, complete headers** (one realistic Chrome/Windows/en-GB set + `Referer`), not
  UA rotation — rotation on a single IP looks *more* bot-like.

## Architecture

Two independent subsystems. **Subsystem 1 (flat-finder fetch) is the priority and ships
first.** Subsystem 2 (Claude Code access) is a follow-on with its own implementation plan.

### Subsystem 1 — Resilient fetch + sources (flat-finder)

```
runner.py
  └─ for each SiteAdapter (rightmove, openrent, zoopla):
        adapter.fetch_listings(zone, search_params)
            ├─ uses its Fetcher (HttpFetcher | FlareSolverrFetcher)
            └─ parses transport output → list[listing dict]
```

**`Fetcher` protocol** (`flat_finder/scraper/fetch.py`) — "get me the bytes for a URL":

- `get(url, *, headers=None) -> FetchResult` where `FetchResult` carries
  `status`, `text`, `ok`, and `challenged` (bool — solver/anti-bot challenge detected).
- **`HttpFetcher`** — a configured `requests.Session` (one per run, cookie + keep-alive
  persistence) with a mounted `HTTPAdapter(max_retries=Retry(...))`, coherent default
  headers, and a jittered inter-request delay. Used by Rightmove + OpenRent.
- **`FlareSolverrFetcher`** — POSTs `{"cmd":"request.get","url":...,"maxTimeout":...}` to
  `http://flaresolverr:8191/v1`, returns the solved HTML; sets `challenged=True` on
  `status:"error"` / challenge markers. Used by Zoopla. FlareSolverr URL is config
  (`FLARESOLVERR_URL`, default `http://flaresolverr:8191`).
- **Future swap-ins (documented, not built):** `CurlCffiFetcher` (TLS impersonation if a
  light source starts TLS-blocking), `ByparrFetcher` (heavier Cloudflare solver — same
  FlareSolverr API, drop-in), managed-API fetcher.

**`SiteAdapter`** — one per source (the existing `rightmove.py` / `openrent.py` modules,
refactored; new `zoopla.py`). Each declares:
- which `Fetcher` tier it uses,
- URL template(s) for a zone + search params,
- an `extract(text) -> list[dict]` parser producing the existing listing dict shape.

**Per-source config** (`flat_finder/config.py` / env): `enabled`, `frequency` (loop
multiplier — Zoopla can later be made less frequent than Rightmove without code change),
and `egress` (default `residential`; `vpn` reserved as a future experiment flag).

**Source specifics:**
- **Rightmove** → migrate from `find.html` + `__NEXT_DATA__` HTML parsing to the
  `www.rightmove.co.uk/api/_search?...&channel=RENT&index=N` JSON endpoint (more robust
  against HTML-shape drift). Same 1,050-result/42-page cap; same pagination via `index`.
- **OpenRent** → unchanged parsing, moved onto `HttpFetcher`.
- **Zoopla** → `FlareSolverrFetcher` fetches the rendered search page; `extract` parses the
  rendered HTML cards (listing IDs via `/to-rent/details/<id>`, price, address — proven
  present) with the RSC `self.__next_f` chunks as a secondary source. Detail-page enrichment
  later if needed.

**Instrumentation:**
- Log per source: fetch outcome, HTTP status, `challenged` flag, listing count, latency.
- Prometheus metrics (the Pi already runs Prometheus/cAdvisor/Grafana): counters for
  `scrape_fetch_total{source,result}`, `scrape_challenge_total{source}`, and a latency
  histogram. Lets us see FlareSolverr contention with Prowlarr/EZTV and Zoopla
  challenge-rate with real numbers before deciding to scale (e.g. lower Zoopla frequency,
  or swap to Byparr).

**Error handling:** each source already runs inside `_scrape_source` (catches + logs,
returns `[]`), so one source failing never kills the run. `HttpFetcher` handles transient
5xx/Retry-After internally; `FlareSolverrFetcher` surfaces `challenged` so the runner logs
it and moves on. Partial pagination results are kept, not discarded.

### Subsystem 2 — Claude Code web access (follow-on)

- **SearXNG** container on `pi-net` (official multi-arch arm64 image), with
  `formats: [html, json]` enabled and the `reddit` engine on — sidesteps the Reddit/search
  block. Lean on DuckDuckGo/Brave/Reddit engines (Google rate-limits a single IP).
- **Search MCP:** `mcp-searxng` pointed at the local SearXNG, registered with Claude Code.
- **Fetch (blocked pages):** a thin MCP (or reuse) that can route a URL through the existing
  FlareSolverr for Cloudflare-walled pages; plain fetch otherwise.
- This subsystem shares no code with Subsystem 1 beyond optionally reusing
  `FlareSolverrFetcher`'s endpoint — so it gets its own spec + plan.

## File structure (Subsystem 1)

- **Create** `flat_finder/scraper/fetch.py` — `Fetcher` protocol, `FetchResult`,
  `HttpFetcher`, `FlareSolverrFetcher`, session/Retry factory.
- **Create** `flat_finder/scraper/zoopla.py` — Zoopla `SiteAdapter` (URL build + extract).
- **Modify** `flat_finder/scraper/rightmove.py` — switch to `/api/_search`, use a `Fetcher`,
  return partial results on failure.
- **Modify** `flat_finder/scraper/openrent.py` — use `HttpFetcher`.
- **Modify** `flat_finder/scraper/runner.py` — iterate a `SiteAdapter` registry; per-source
  config; emit metrics/logs.
- **Modify** `flat_finder/scraping.py` — upgrade `HTTP_HEADERS` to the full coherent set.
- **Modify** `flat_finder/config.py` — per-source config + `FLARESOLVERR_URL`.
- **Modify** `docker-compose.yml` — ensure the scraper can reach `flaresolverr:8191` on
  `pi-net` (FlareSolverr lives in the mediastack compose; confirm shared network).
- **Tests** under `tests/`: `test_fetch.py` (Retry config, partial results, challenge
  detection — mocked HTTP), `test_zoopla.py` (extract from a saved fixture), updated
  `test_scraper.py`.

## Testing strategy

TDD, matching the repo. Unit-test each `Fetcher` and `SiteAdapter` against **saved HTML/JSON
fixtures** (capture one real Rightmove `_search` JSON, one OpenRent page, one FlareSolverr
Zoopla response) — no live network in tests. Cover: Retry mounts 503 in `status_forcelist`;
partial-results-on-failure; `challenged` detection; each `extract` produces the right listing
dicts incl. lat/lng where available. E2E/integration unchanged.

## Rollout

Branch `feat/resilient-scraping-layer` → PR → review → merge → `git pull` on Pi → rebuild
the scraper (`docker compose ... up -d --build flat-finder-scraper`). Watch Grafana for
Zoopla challenge-rate and FlareSolverr contention over the first few cycles; dial Zoopla
frequency via config if needed. Subsystem 2 (SearXNG + MCP) is a separate PR.

## Risks & mitigations

- **FlareSolverr stops clearing Zoopla** (Cloudflare changes; community reports FlareSolverr
  weakening). → `challenged` logging makes it visible; **Byparr** is a known-good, re-addable
  drop-in (same API), managed API behind that.
- **FlareSolverr contention** with Prowlarr/EZTV (shared, 512 MB, one browser). → measure via
  Prometheus first; if it bites, lower Zoopla frequency or give the solver more headroom.
- **Cloudflare rate-limits the residential IP** under the 15-min loop. → per-source frequency
  knob to back off; failures are logged, not silent.
- **ToS / legal.** Scraping breaches site ToS (civil, not criminal); Zoopla adds active
  anti-bot circumvention. Mitigated by keeping use **private, personal, non-republished**
  (local UI behind Tailscale), low volume, linking back rather than mirroring content.

## Open questions

- Zoopla detail-page enrichment (sqft, full description) — defer until search-card data
  proves insufficient?
- Exact Prometheus metric names / whether to reuse an existing exporter pattern.
- Subsystem 2 fetch-MCP: build a thin FlareSolverr-backed MCP vs adopt an existing one.
