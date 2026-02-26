# scraper/scraper.py
import logging
from pathlib import Path
from shared.models import init_db, get_connection, insert_listing, get_state, set_state
from shared.config import (DB_PATH, RIGHTMOVE_LOCATION_ID, SEARCH_RADIUS_MILES,
                           MIN_BEDROOMS, MAX_BEDROOMS, MAX_RENT_PCM,
                           NTFY_TOPIC, GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
from scraper.rightmove import fetch_rightmove
from scraper.openrent import fetch_openrent
from scraper.notifier import (format_ntfy_message, format_email_html,
                               send_ntfy, send_email,
                               format_failure_message, format_recovery_message)

log = logging.getLogger("flat-finder")

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
        log.error(f"{name} scrape failed: {e}")
        listings = []
        error = str(e)
    return listings, error

def _handle_failure_state(conn, source: str, error: str | None) -> None:
    state_key = f"{source}_failing"
    was_failing = get_state(conn, state_key) is not None
    if error and not was_failing:
        set_state(conn, state_key, error)
        if NTFY_TOPIC:
            title, body = format_failure_message(source, error)
            send_ntfy(NTFY_TOPIC, title, body)
    elif not error and was_failing:
        conn.execute("DELETE FROM scraper_state WHERE key = ?", (state_key,))
        conn.commit()
        if NTFY_TOPIC:
            title, body = format_recovery_message(source)
            send_ntfy(NTFY_TOPIC, title, body)

def run() -> None:
    init_db(DB_PATH)
    conn = get_connection(DB_PATH)
    first_run = is_first_run(conn)

    rm_listings, rm_error = _scrape_source(
        "rightmove",
        lambda: fetch_rightmove(RIGHTMOVE_LOCATION_ID, SEARCH_RADIUS_MILES,
                                MIN_BEDROOMS, MAX_BEDROOMS, MAX_RENT_PCM),
        conn,
    )
    or_listings, or_error = _scrape_source(
        "openrent",
        lambda: fetch_openrent("Finchley Road Station", SEARCH_RADIUS_MILES,
                               MIN_BEDROOMS, MAX_BEDROOMS, MAX_RENT_PCM),
        conn,
    )

    _handle_failure_state(conn, "rightmove", rm_error)
    _handle_failure_state(conn, "openrent", or_error)

    all_listings = rm_listings + or_listings
    new_listings = process_new_listings(conn, all_listings)

    if first_run:
        set_state(conn, "initialised", "true")
        log.info(f"First run: found {len(all_listings)} existing listings")
        if NTFY_TOPIC:
            send_ntfy(NTFY_TOPIC, "Flat Finder initialised",
                      f"Found {len(all_listings)} existing listings. Future notifications for new ones only.")
    elif new_listings:
        log.info(f"Found {len(new_listings)} new listings")
        if NTFY_TOPIC:
            title, body = format_ntfy_message(new_listings)
            send_ntfy(NTFY_TOPIC, title, body)
        if GMAIL_ADDRESS and GMAIL_APP_PASSWORD:
            html = format_email_html(new_listings)
            send_email(GMAIL_ADDRESS, GMAIL_APP_PASSWORD,
                       f"Flat Finder: {len(new_listings)} new listing{'s' if len(new_listings) != 1 else ''}",
                       html)
    else:
        log.info("No new listings found")

    conn.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    run()
