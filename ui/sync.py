import requests
import logging
from shared.models import get_connection, insert_listing, get_state, set_state
from shared.config import API_BASE_URL, API_KEY

log = logging.getLogger("flat-finder-sync")


def sync_from_vps(db_path) -> int:
    conn = get_connection(db_path)
    last_sync = get_state(conn, "last_sync")
    params = {}
    if last_sync:
        params["since"] = last_sync
    params["limit"] = 200
    headers = {"X-API-Key": API_KEY}
    try:
        resp = requests.get(
            f"{API_BASE_URL}/listings", params=params,
            headers=headers, timeout=30,
        )
        resp.raise_for_status()
    except Exception as e:
        log.error(f"Sync failed: {e}")
        conn.close()
        return 0
    listings = resp.json()
    new_count = 0
    latest_seen = last_sync
    for listing in listings:
        if insert_listing(conn, listing):
            new_count += 1
        if not latest_seen or listing["first_seen"] > latest_seen:
            latest_seen = listing["first_seen"]
    if latest_seen:
        set_state(conn, "last_sync", latest_seen)
    conn.close()
    log.info(f"Synced {new_count} new listings from VPS")
    return new_count
