import logging
import time
from collections.abc import Callable
from typing import Any

import requests

from flat_finder.pois.dao import POICommuteDAO
from flat_finder.pois.model import POI

log = logging.getLogger("flat-finder")

TFL_MODES = "tube,bus,overground,elizabeth-line,dlr,tram"
TFL_RATE_LIMIT_SLEEP_S = 0.5


def tfl_journey_mins(
    from_lat: float, from_lng: float, to_lat: float, to_lng: float, arrive_by: str = "0830"
) -> int | None:
    """Query TfL Journey Planner for shortest journey duration in minutes."""
    url = f"https://api.tfl.gov.uk/Journey/JourneyResults/{from_lat},{from_lng}/to/{to_lat},{to_lng}"
    try:
        resp = requests.get(
            url,
            params={
                "mode": TFL_MODES,
                "time": arrive_by,
                "timeIs": "arriving",
            },
            timeout=15,
        )
        resp.raise_for_status()
        journeys = resp.json().get("journeys", [])
        if not journeys:
            return None
        return min(j["duration"] for j in journeys)
    except requests.RequestException:
        log.exception("TfL journey lookup failed")
        return None


def fetch_commutes_for_listings(
    commute_dao: POICommuteDAO,
    poi: POI,
    rows: list[dict[str, Any]],
    after_upsert: Callable[[], None] | None = None,
) -> None:
    """Fetch TfL commutes for the given listings and upsert results. Throttled.

    `after_upsert` runs after each successful upsert (e.g. a per-row commit when
    called from a long-lived background thread).
    """
    for row in rows:
        mins = tfl_journey_mins(row["latitude"], row["longitude"], poi.lat, poi.lng)
        if mins is None:
            # TfL failure — no commute fetched, skip the rate-limit sleep
            continue
        commute_dao.upsert(row["id"], poi.id, mins)
        if after_upsert:
            after_upsert()
        time.sleep(TFL_RATE_LIMIT_SLEEP_S)
