import json
import logging
import re
from collections.abc import Callable
from typing import Any

from shapely.geometry import Point, shape
from shapely.prepared import prep
from sqlalchemy.orm import Session

from flat_finder import config
from flat_finder.database import get_engine, get_session
from flat_finder.listings.persistence import ListingRepository, ListingStateRepository, ScraperStateDB
from flat_finder.pois.persistence import POICommuteRepository, POIRepository
from flat_finder.scraper.commute import fetch_commutes_for_listings
from flat_finder.scraper.notifier import (
    format_email_html,
    format_failure_message,
    format_ntfy_single,
    format_recovery_message,
    send_email,
    send_ntfy,
)
from flat_finder.scraper.openrent import fetch_openrent
from flat_finder.scraper.rightmove import fetch_rightmove
from flat_finder.scraper.transitous import TransitousCommuteClient
from flat_finder.scraping import make_retry_session
from flat_finder.users.persistence import UserRepository
from flat_finder.zones.persistence import ListingZoneRepository, ZoneRepository

log = logging.getLogger("flat-finder")

KM_PER_MILE = 1.60934
DEFAULT_ZONE_RADIUS_KM = 1.6
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


def _filter_listings_by_zone(listings: list[dict[str, Any]], zone_geometry: str | None) -> list[dict[str, Any]]:
    """Keep only listings inside the zone polygon. Keep those without coords.

    Pre-parses and prepares the polygon once so the per-listing contains() is fast
    (shapely's prepared geometry is much cheaper for many point-in-polygon tests).
    """
    if not zone_geometry:
        return listings
    prepared = prep(shape(json.loads(zone_geometry)))
    return [
        listing
        for listing in listings
        if not (listing.get("latitude") and listing.get("longitude"))
        or prepared.contains(Point(listing["longitude"], listing["latitude"]))
    ]


def _get_scraper_state(session: Session, key: str) -> str | None:
    row = session.get(ScraperStateDB, key)
    return row.value if row else None


def _set_scraper_state(session: Session, key: str, value: str) -> None:
    row = session.get(ScraperStateDB, key)
    if row is None:
        row = ScraperStateDB(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    session.flush()


def _delete_scraper_state(session: Session, key: str) -> None:
    row = session.get(ScraperStateDB, key)
    if row:
        session.delete(row)
        session.flush()


def _handle_failure_state(
    session: Session,
    ntfy_topic: str | None,
    source: str,
    error: str | None,
) -> None:
    state_key = f"{source}_failing"
    was_failing = _get_scraper_state(session, state_key) is not None
    if error and not was_failing:
        _set_scraper_state(session, state_key, error)
        if ntfy_topic:
            title, body = format_failure_message(source, error)
            _notify_safe(send_ntfy, ntfy_topic, title, body)
    elif not error and was_failing:
        _delete_scraper_state(session, state_key)
        if ntfy_topic:
            title, body = format_recovery_message(source)
            _notify_safe(send_ntfy, ntfy_topic, title, body)


def run() -> None:  # noqa: C901, PLR0912, PLR0915
    engine = get_engine(config.DB_PATH)
    Session = get_session(engine)  # noqa: N806
    session = Session()
    try:
        listing_repo = ListingRepository(session)
        listing_state_repo = ListingStateRepository(session)
        listing_zone_repo = ListingZoneRepository(session)
        zone_repo = ZoneRepository(session)
        poi_repo = POIRepository(session)
        poi_commute_repo = POICommuteRepository(session)
        user_repo = UserRepository(session)

        first_run = _get_scraper_state(session, "initialised") is None

        all_zones = zone_repo.get_all()

        # Scrape per zone, dedup listings globally
        # Map listing_id -> list of zone IDs that found it
        listing_zone_map: dict[str, list[int]] = {}
        all_listings: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        seen_fingerprints: set[tuple[str, int, int]] = set()

        # Compute search params: widest range across all users, fall back to config defaults
        all_users = user_repo.get_all()
        user_rents = [u.max_rent_pcm for u in all_users if u.max_rent_pcm]
        user_min_beds = [u.min_bedrooms for u in all_users if u.min_bedrooms is not None]
        user_max_beds = [u.max_bedrooms for u in all_users if u.max_bedrooms is not None]
        search_max_rent = max(user_rents) if user_rents else config.MAX_RENT_PCM
        search_min_beds = min(user_min_beds) if user_min_beds else config.MIN_BEDROOMS
        search_max_beds = max(user_max_beds) if user_max_beds else config.MAX_BEDROOMS
        log.info("Search params (widest): rent=%d, beds=%d-%d", search_max_rent, search_min_beds, search_max_beds)

        # Use first user's ntfy_topic for failure/recovery notifications (global scraper health)
        users_with_ntfy = user_repo.get_all_with_ntfy()
        health_ntfy_topic = users_with_ntfy[0].ntfy_topic if users_with_ntfy else None

        # One session per run: keep-alive + cookies persist across zones, and
        # transient 429/5xx responses are retried with backoff (see make_retry_session)
        http_session = make_retry_session()

        for zone in all_zones:
            radius_km = zone.covering_radius_km or DEFAULT_ZONE_RADIUS_KM
            rm_radius_miles = radius_km / KM_PER_MILE
            or_radius_km = int(radius_km)

            rm_listings, rm_error = _scrape_source(
                f"rightmove/{zone.name}",
                lambda z=zone, r=rm_radius_miles: fetch_rightmove(
                    z.rightmove_id or "", r, search_min_beds, search_max_beds, search_max_rent, session=http_session
                ),
            )
            or_listings, or_error = _scrape_source(
                f"openrent/{zone.name}",
                lambda z=zone, r=or_radius_km: fetch_openrent(
                    z.openrent_term or "", r, search_min_beds, search_max_beds, search_max_rent, session=http_session
                ),
            )

            _handle_failure_state(session, health_ntfy_topic, f"rightmove/{zone.name}", rm_error)
            _handle_failure_state(session, health_ntfy_topic, f"openrent/{zone.name}", or_error)

            # Post-filter by polygon
            combined = _filter_listings_by_zone(rm_listings + or_listings, zone.geometry)

            for listing in combined:
                # Track that this zone found this listing (before global dedup)
                if listing["id"] not in listing_zone_map:
                    listing_zone_map[listing["id"]] = []
                listing_zone_map[listing["id"]].append(zone.id)

                if listing["id"] in seen_ids:
                    continue
                # Cross-source dedup: same address + price + bedrooms = same flat
                fp = _listing_fingerprint(listing)
                if fp and fp in seen_fingerprints:
                    log.debug("Skipping cross-source duplicate: %s", listing["id"])
                    continue
                listing["zone"] = zone.name
                all_listings.append(listing)
                seen_ids.add(listing["id"])
                if fp:
                    seen_fingerprints.add(fp)

        # Insert new listings and link to zones
        new_listings: list[dict[str, Any]] = []
        for listing in all_listings:
            is_new = listing_repo.insert(listing)
            # Always link to all zones that found this listing (INSERT OR IGNORE)
            for zone_id in listing_zone_map.get(listing["id"], []):
                listing_zone_repo.link(listing["id"], zone_id)
            if is_new:
                new_listings.append(listing)

        # Release the write lock before the slow commute phase — holding one
        # transaction across minutes of network I/O starves UI writes past
        # their busy_timeout ("database is locked" 500s).
        session.commit()

        pois = poi_repo.get_all()
        commute_client = TransitousCommuteClient()

        # Fetch commute times for new listings (per POI), committing per upsert
        if new_listings and pois:
            rows = [
                {"id": listing["id"], "latitude": listing["latitude"], "longitude": listing["longitude"]}
                for listing in new_listings
                if listing.get("latitude") and listing.get("longitude")
            ]
            for poi in pois:
                fetch_commutes_for_listings(poi_commute_repo, poi, rows, commute_client, after_upsert=session.commit)

        # Backfill: any listings still missing commute data for any POI
        for poi in pois:
            missing = poi_commute_repo.get_listings_missing_poi(poi.id)
            if missing:
                log.info("Backfilling '%s' commute for %d listings", poi.name, len(missing))
                fetch_commutes_for_listings(poi_commute_repo, poi, missing, commute_client, after_upsert=session.commit)

        # Attach poi_commutes to new listings for notification (one batched query)
        if new_listings:
            commutes = poi_commute_repo.get_for_listings([listing["id"] for listing in new_listings])
            for listing in new_listings:
                listing["poi_commutes"] = commutes.get(listing["id"], {})

        # Archive listings older than the retention window. Guarded so an
        # archiving failure can't abort the run before notifications go out.
        try:
            archived_ids = listing_repo.archive_old(PRUNE_AFTER_DAYS)
            if archived_ids:
                listing_state_repo.delete_for_listings(archived_ids)
                poi_commute_repo.delete_for_listings(archived_ids)
                listing_zone_repo.delete_for_listings(archived_ids)
                log.info("Archived %d listings older than %d days", len(archived_ids), PRUNE_AFTER_DAYS)
        except Exception:
            session.rollback()
            log.exception("Archiving old listings failed")

        if first_run:
            _set_scraper_state(session, "initialised", "true")
            log.info("First run: found %d existing listings", len(all_listings))
            if health_ntfy_topic:
                _notify_safe(
                    send_ntfy,
                    health_ntfy_topic,
                    "Flat Finder initialised",
                    f"Found {len(all_listings)} existing listings across {len(all_zones)} zones.",
                )
        elif new_listings:
            log.info("Found %d new listings", len(new_listings))
            # Per-user ntfy notifications
            for user in users_with_ntfy:
                if not user.ntfy_topic:
                    continue
                user_zone_ids = [z.id for z in zone_repo.get_by_user(user.id)]
                user_listing_ids = set(listing_zone_repo.get_listing_ids_for_zones(user_zone_ids))
                user_new = [lst for lst in new_listings if lst["id"] in user_listing_ids]
                if user_new:
                    user_pois = poi_repo.get_by_user(user.id)
                    poi_dicts = [{"id": p.id, "name": p.name} for p in user_pois]
                    for listing in user_new:
                        title, body = format_ntfy_single(listing, poi_dicts)
                        _notify_safe(send_ntfy, user.ntfy_topic, title, body, click_url=listing.get("url"))

            # Global email notification (all new listings, not per-user)
            if config.GMAIL_ADDRESS and config.GMAIL_APP_PASSWORD:
                html = format_email_html(new_listings)
                _notify_safe(
                    send_email,
                    config.GMAIL_ADDRESS,
                    config.GMAIL_APP_PASSWORD,
                    f"Flat Finder: {len(new_listings)} new listing{'s' if len(new_listings) != 1 else ''}",
                    html,
                )
        else:
            log.info("No new listings found")

        session.commit()
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    run()
