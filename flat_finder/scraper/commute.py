import logging
import time
from collections.abc import Callable
from typing import Any, Protocol

from flat_finder.pois.dao import POICommuteDAO
from flat_finder.pois.model import POI

log = logging.getLogger("flat-finder")

NO_JOURNEY = -1

RATE_LIMIT_SLEEP_S = 0.5


class CommuteClient(Protocol):
    """Facade: resolve transit commute time between two coordinates."""

    def journey_mins(
        self, from_lat: float, from_lng: float, to_lat: float, to_lng: float
    ) -> int | None:
        """Return shortest journey in minutes.

        Returns NO_JOURNEY (-1) when no route exists (permanent),
        None on transient failures (worth retrying next run).
        """
        ...


def fetch_commutes_for_listings(
    commute_dao: POICommuteDAO,
    poi: POI,
    rows: list[dict[str, Any]],
    commute_client: CommuteClient,
    after_upsert: Callable[[], None] | None = None,
) -> None:
    """Fetch commutes for the given listings and upsert results. Throttled."""
    for row in rows:
        mins = commute_client.journey_mins(row["latitude"], row["longitude"], poi.lat, poi.lng)
        if mins is None:
            continue
        commute_dao.upsert(row["id"], poi.id, mins)
        if after_upsert:
            after_upsert()
        time.sleep(RATE_LIMIT_SLEEP_S)
