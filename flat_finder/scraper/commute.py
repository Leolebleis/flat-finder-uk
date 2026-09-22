import logging
import time
from collections.abc import Callable
from typing import Any, Protocol

from flat_finder.pois.dao import POICommuteDAO
from flat_finder.pois.model import POI

log = logging.getLogger("flat-finder")

NO_JOURNEY = -1

RATE_LIMIT_SLEEP_S = 0.5

# Listings rounded to this many decimal places (~1m) share one commute query.
# The commute from points this close is identical, so co-located listings
# (same building, dev pin) need only one upstream call.
_COORD_PRECISION = 5


class CommuteClient(Protocol):
    """Facade: resolve transit commute time between two coordinates."""

    def journey_mins(self, from_lat: float, from_lng: float, to_lat: float, to_lng: float) -> int | None:
        """Return shortest journey in minutes.

        Returns NO_JOURNEY (-1) when no route exists (permanent),
        None on transient failures (worth retrying next run).
        """
        ...


def fetch_commutes_for_listings(  # noqa: PLR0913
    commute_dao: POICommuteDAO,
    poi: POI,
    rows: list[dict[str, Any]],
    commute_client: CommuteClient,
    after_upsert: Callable[[], None] | None = None,
    max_calls: int | None = None,
) -> None:
    """Fetch commutes for the given listings and upsert results. Throttled.

    Listings sharing a coordinate (rounded to ~1m) are queried once and the
    result reused for all of them, cutting redundant calls to the upstream
    service. Each listing still gets its own row.

    `max_calls` caps the upstream requests made here. It is applied after
    grouping, so the cap counts real requests rather than listings, and a
    coordinate is never split across the boundary — callers that defer the
    remainder to a later pass would otherwise re-request the same coordinate.
    """
    groups: dict[tuple[float, float], list[dict[str, Any]]] = {}
    for row in rows:
        key = (round(row["latitude"], _COORD_PRECISION), round(row["longitude"], _COORD_PRECISION))
        groups.setdefault(key, []).append(row)

    selected = list(groups.values())
    if max_calls is not None and len(selected) > max_calls:
        log.info(
            "Commute prefetch for '%s' capped at %d of %d coordinates; rest deferred to backfill",
            poi.name,
            max_calls,
            len(selected),
        )
        selected = selected[:max_calls]

    for group in selected:
        head = group[0]
        mins = commute_client.journey_mins(head["latitude"], head["longitude"], poi.lat, poi.lng)
        if mins is None:
            continue  # transient — retry the whole coordinate next run
        for row in group:
            commute_dao.upsert(row["id"], poi.id, mins)
            if after_upsert:
                after_upsert()
        time.sleep(RATE_LIMIT_SLEEP_S)
