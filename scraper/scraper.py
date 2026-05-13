# scraper/scraper.py
import logging
import re
import time

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


def _normalize_address(addr: str) -> str:
    """Normalize address for dedup: lowercase, strip punctuation, collapse whitespace."""
    addr = addr.lower().strip()
    addr = re.sub(r"[,.\-']", " ", addr)
    addr = re.sub(r"\s+", " ", addr)
    # Strip "london" which one source may include and the other may not
    addr = re.sub(r"\blondon\b", "", addr)
    addr = re.sub(r"\s+", " ", addr)
    return addr.strip()


def _listing_fingerprint(listing: dict) -> tuple | None:
    """Return a (normalized_address, price, bedrooms) tuple for cross-source dedup."""
    addr = listing.get("address")
    price = listing.get("price_pcm")
    beds = listing.get("bedrooms")
    if not addr or price is None or beds is None:
        return None
    return (_normalize_address(addr), price, beds)


def is_first_run(conn) -> bool:
    return get_state(conn, "initialised") is None


def process_new_listings(conn, listings: list[dict]) -> list[dict]:
    new = []
    for listing in listings:
        if insert_listing(conn, listing):
            new.append(listing)
    return new


def _scrape_source(name: str, fetch_fn, conn) -> tuple[list[dict], str | None]:
    try:
        listings = fetch_fn()
        error = None
    except Exception as e:
        log.exception(f"{name} scrape failed: {e}")
        listings = []
        error = str(e)
    return listings, error


def _notify_safe(fn, *args, **kwargs) -> None:
    try:
        fn(*args, **kwargs)
    except Exception as e:
        log.exception(f"Notification failed: {e}")


def _handle_failure_state(conn, source: str, error: str | None) -> None:
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


def _filter_listings_by_zone(listings: list[dict], zone: dict) -> list[dict]:
    """Keep only listings inside the zone polygon. Keep those without coords."""
    geom_str = zone.get("geometry")
    if not geom_str:
        return listings
    return [
        l
        for l in listings
        if not (l.get("latitude") and l.get("longitude")) or point_in_zone(l["latitude"], l["longitude"], geom_str)
    ]


def run() -> None:
    init_db(DB_PATH)
    conn = get_connection(DB_PATH)
    first_run = is_first_run(conn)
    zones = [dict(z) for z in get_zones(conn)]

    all_listings = []
    seen_ids = set()
    seen_fingerprints = set()

    for zone in zones:
        # DB zones store covering_radius_km; convert to miles for Rightmove
        radius_km = zone.get("covering_radius_km", 1.6)  # ~1 mile default
        rm_radius_miles = radius_km / 1.60934
        or_radius_km = radius_km

        rm_listings, rm_error = _scrape_source(
            f"rightmove/{zone['name']}",
            lambda z=zone, r=rm_radius_miles: fetch_rightmove(
                z.get("rightmove_id", ""), r, MIN_BEDROOMS, MAX_BEDROOMS, MAX_RENT_PCM
            ),
            conn,
        )
        or_listings, or_error = _scrape_source(
            f"openrent/{zone['name']}",
            lambda z=zone, r=or_radius_km: fetch_openrent(
                z.get("openrent_term", ""), r, MIN_BEDROOMS, MAX_BEDROOMS, MAX_RENT_PCM
            ),
            conn,
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
                log.debug(f"Skipping cross-source duplicate: {listing['id']}")
                continue
            listing["zone"] = zone["name"]
            all_listings.append(listing)
            seen_ids.add(listing["id"])
            if fp:
                seen_fingerprints.add(fp)

    new_listings = process_new_listings(conn, all_listings)

    # Load POIs from database
    pois = get_pois(conn)

    # Fetch commute times for new listings
    for listing in new_listings:
        if listing.get("latitude") and listing.get("longitude"):
            for poi in pois:
                mins = tfl_journey_mins(listing["latitude"], listing["longitude"], poi["lat"], poi["lng"])
                if mins is not None:
                    upsert_poi_commute(conn, listing["id"], poi["id"], mins)
                time.sleep(0.5)

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
                log.info(f"Backfilling '{poi['name']}' commute for {len(missing)} listings")
                for row in missing:
                    mins = tfl_journey_mins(row["latitude"], row["longitude"], poi["lat"], poi["lng"])
                    if mins is not None:
                        upsert_poi_commute(conn, row["id"], poi["id"], mins)
                    time.sleep(0.5)

    # Attach poi_commutes to new listings for notification
    for listing in new_listings:
        commute_rows = conn.execute(
            "SELECT poi_id, commute_mins FROM poi_commutes WHERE listing_id = ?",
            (listing["id"],),
        ).fetchall()
        listing["poi_commutes"] = {row["poi_id"]: row["commute_mins"] for row in commute_rows}

    # Prune listings older than 2 weeks
    pruned = conn.execute("DELETE FROM listings WHERE first_seen < datetime('now', '-14 days')").rowcount
    if pruned:
        conn.execute("DELETE FROM user_state WHERE listing_id NOT IN (SELECT id FROM listings)")
        conn.execute("DELETE FROM poi_commutes WHERE listing_id NOT IN (SELECT id FROM listings)")
        conn.commit()
        log.info(f"Pruned {pruned} listings older than 2 weeks")

    if first_run:
        set_state(conn, "initialised", "true")
        log.info(f"First run: found {len(all_listings)} existing listings")
        if NTFY_TOPIC:
            _notify_safe(
                send_ntfy,
                NTFY_TOPIC,
                "Flat Finder initialised",
                f"Found {len(all_listings)} existing listings across {len(zones)} zones.",
            )
    elif new_listings:
        log.info(f"Found {len(new_listings)} new listings")
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
