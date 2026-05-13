import logging
import re
import sqlite3
import time
from collections.abc import Callable
from typing import Any

from shared.config import (
    DB_PATH,
    GMAIL_ADDRESS,
    GMAIL_APP_PASSWORD,
    MAX_BEDROOMS,
    MAX_RENT_PCM,
    MIN_BEDROOMS,
    NTFY_TOPIC,
)
from shared.models import (
    get_connection,
    get_pois,
    get_state,
    get_zones,
    init_db,
    insert_listing,
    set_state,
    upsert_poi_commute,
)
from shared.zones import point_in_zone

from scraper.commute import tfl_journey_mins
from scraper.notifier import (
    format_email_html,
    format_failure_message,
    format_ntfy_message,
    format_recovery_message,
    send_email,
    send_ntfy,
)
from scraper.openrent import fetch_openrent
from scraper.rightmove import fetch_rightmove

log = logging.getLogger("flat-finder")

KM_PER_MILE = 1.60934
DEFAULT_ZONE_RADIUS_KM = 1.6
TFL_RATE_LIMIT_SLEEP_S = 0.5
PRUNE_AFTER_DAYS = 14


def _normalize_address(addr: str) -> str:
    """Normalize address for dedup: lowercase, strip punctuation, collapse whitespace."""
    addr = addr.lower().strip()
    addr = re.sub(r"[,.\-']", " ", addr)
    addr = re.sub(r"\s+", " ", addr)
    # Strip "london" which one source may include and the other may not
    addr = re.sub(r"\blondon\b", "", addr)
    addr = re.sub(r"\s+", " ", addr)
    return addr.strip()


def _listing_fingerprint(listing: dict[str, Any]) -> tuple[str, int, int] | None:
    """Return a (normalized_address, price, bedrooms) tuple for cross-source dedup."""
    addr = listing.get("address")
    price = listing.get("price_pcm")
    beds = listing.get("bedrooms")
    if not addr or price is None or beds is None:
        return None
    return (_normalize_address(addr), price, beds)


def is_first_run(conn: sqlite3.Connection) -> bool:
    return get_state(conn, "initialised") is None


def process_new_listings(conn: sqlite3.Connection, listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [listing for listing in listings if insert_listing(conn, listing)]


def _scrape_source(
    name: str,
    fetch_fn: Callable[[], list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        listings = fetch_fn()
    except Exception as e:
        log.exception("%s scrape failed", name)
        return [], str(e)
    return listings, None


def _notify_safe(fn: Callable[..., Any], *args: object, **kwargs: object) -> None:
    try:
        fn(*args, **kwargs)
    except Exception:
        log.exception("Notification failed")


def _handle_failure_state(conn: sqlite3.Connection, source: str, error: str | None) -> None:
    state_key = f"{source}_failing"
    was_failing = get_state(conn, state_key) is not None
    if error and not was_failing:
        set_state(conn, state_key, error)
        if NTFY_TOPIC:
            title, body = format_failure_message(source, error)
            _notify_safe(send_ntfy, NTFY_TOPIC, title, body)
    elif not error and was_failing:
        conn.execute("DELETE FROM scraper_state WHERE key = ?", (state_key,))
        conn.commit()
        if NTFY_TOPIC:
            title, body = format_recovery_message(source)
            _notify_safe(send_ntfy, NTFY_TOPIC, title, body)


def _filter_listings_by_zone(listings: list[dict[str, Any]], zone: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep only listings inside the zone polygon. Keep those without coords."""
    geom_str = zone.get("geometry")
    if not geom_str:
        return listings
    return [
        listing
        for listing in listings
        if not (listing.get("latitude") and listing.get("longitude"))
        or point_in_zone(listing["latitude"], listing["longitude"], geom_str)
    ]


def run() -> None:  # noqa: C901, PLR0912, PLR0915
    init_db(DB_PATH)
    conn = get_connection(DB_PATH)
    first_run = is_first_run(conn)
    zones = [dict(z) for z in get_zones(conn)]

    all_listings = []
    seen_ids = set()
    seen_fingerprints = set()

    for zone in zones:
        # DB zones store covering_radius_km; convert to miles for Rightmove
        radius_km = zone.get("covering_radius_km", DEFAULT_ZONE_RADIUS_KM)
        rm_radius_miles = radius_km / KM_PER_MILE
        or_radius_km = radius_km

        rm_listings, rm_error = _scrape_source(
            f"rightmove/{zone['name']}",
            lambda z=zone, r=rm_radius_miles: fetch_rightmove(
                z.get("rightmove_id", ""), r, MIN_BEDROOMS, MAX_BEDROOMS, MAX_RENT_PCM
            ),
        )
        or_listings, or_error = _scrape_source(
            f"openrent/{zone['name']}",
            lambda z=zone, r=or_radius_km: fetch_openrent(
                z.get("openrent_term", ""), r, MIN_BEDROOMS, MAX_BEDROOMS, MAX_RENT_PCM
            ),
        )

        _handle_failure_state(conn, f"rightmove/{zone['name']}", rm_error)
        _handle_failure_state(conn, f"openrent/{zone['name']}", or_error)

        # Post-filter by polygon
        combined = _filter_listings_by_zone(rm_listings + or_listings, zone)

        for listing in combined:
            if listing["id"] in seen_ids:
                continue
            # Cross-source dedup: same address + price + bedrooms = same flat
            fp = _listing_fingerprint(listing)
            if fp and fp in seen_fingerprints:
                log.debug("Skipping cross-source duplicate: %s", listing["id"])
                continue
            listing["zone"] = zone["name"]
            all_listings.append(listing)
            seen_ids.add(listing["id"])
            if fp:
                seen_fingerprints.add(fp)

    new_listings = process_new_listings(conn, all_listings)
    pois = get_pois(conn)

    # Fetch commute times for new listings
    for listing in new_listings:
        if listing.get("latitude") and listing.get("longitude"):
            for poi in pois:
                mins = tfl_journey_mins(listing["latitude"], listing["longitude"], poi["lat"], poi["lng"])
                if mins is not None:
                    upsert_poi_commute(conn, listing["id"], poi["id"], mins)
                time.sleep(TFL_RATE_LIMIT_SLEEP_S)

    # Backfill: listings missing commute data for any POI
    if pois:
        for poi in pois:
            missing = conn.execute(
                """SELECT l.id, l.latitude, l.longitude FROM listings l
                   WHERE l.latitude IS NOT NULL AND l.longitude IS NOT NULL
                   AND NOT EXISTS (
                       SELECT 1 FROM poi_commutes pc
                       WHERE pc.listing_id = l.id AND pc.poi_id = ?
                   )""",
                (poi["id"],),
            ).fetchall()
            if missing:
                log.info("Backfilling '%s' commute for %d listings", poi["name"], len(missing))
                for row in missing:
                    mins = tfl_journey_mins(row["latitude"], row["longitude"], poi["lat"], poi["lng"])
                    if mins is not None:
                        upsert_poi_commute(conn, row["id"], poi["id"], mins)
                    time.sleep(TFL_RATE_LIMIT_SLEEP_S)

    # Attach poi_commutes to new listings for notification
    for listing in new_listings:
        commute_rows = conn.execute(
            "SELECT poi_id, commute_mins FROM poi_commutes WHERE listing_id = ?",
            (listing["id"],),
        ).fetchall()
        listing["poi_commutes"] = {row["poi_id"]: row["commute_mins"] for row in commute_rows}

    # Prune listings older than 2 weeks
    pruned = conn.execute(
        f"DELETE FROM listings WHERE first_seen < datetime('now', '-{PRUNE_AFTER_DAYS} days')"  # noqa: S608
    ).rowcount
    if pruned:
        conn.execute("DELETE FROM user_state WHERE listing_id NOT IN (SELECT id FROM listings)")
        conn.execute("DELETE FROM poi_commutes WHERE listing_id NOT IN (SELECT id FROM listings)")
        conn.commit()
        log.info("Pruned %d listings older than 2 weeks", pruned)

    if first_run:
        set_state(conn, "initialised", "true")
        log.info("First run: found %d existing listings", len(all_listings))
        if NTFY_TOPIC:
            _notify_safe(
                send_ntfy,
                NTFY_TOPIC,
                "Flat Finder initialised",
                f"Found {len(all_listings)} existing listings across {len(zones)} zones.",
            )
    elif new_listings:
        log.info("Found %d new listings", len(new_listings))
        if NTFY_TOPIC:
            title, body = format_ntfy_message(new_listings, pois)
            click_url = new_listings[0].get("url")
            _notify_safe(send_ntfy, NTFY_TOPIC, title, body, click_url=click_url)
        if GMAIL_ADDRESS and GMAIL_APP_PASSWORD:
            html = format_email_html(new_listings)
            _notify_safe(
                send_email,
                GMAIL_ADDRESS,
                GMAIL_APP_PASSWORD,
                f"Flat Finder: {len(new_listings)} new listing{'s' if len(new_listings) != 1 else ''}",
                html,
            )
    else:
        log.info("No new listings found")

    conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    run()
