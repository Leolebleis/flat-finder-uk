"""Transitous API client — UK-wide public transit commute times.

Transitous is a community-run routing service (transitous.org) backed by MOTIS,
covering all of Great Britain (buses, rail, tube, coach). Replaces TfL Journey
Planner which only covers the London bounding box.
"""

import logging
import time
from datetime import UTC, datetime, timedelta

import requests

from flat_finder.scraper.commute import NO_JOURNEY

log = logging.getLogger("flat-finder")

TRANSITOUS_API = "https://api.transitous.org/api/v6/plan"
USER_AGENT = "flat-finder/1.0 (leo.lebleis@gmail.com)"

# When an origin returns no itineraries, MOTIS sometimes can't snap that exact
# coordinate onto its walkable network (e.g. a seafront / edge-of-grid pin) even
# though points ~100m away route fine. Before declaring a pair permanently
# unroutable, retry from a small ring of nudged origins (~150m). First hit wins;
# +lat (inland) is tried first since coastal dead-spots sit at the south edge.
_NUDGE_DEG = 0.0015  # ~150m latitude, ~95m longitude at UK latitudes
_NUDGE_OFFSETS = ((_NUDGE_DEG, 0.0), (0.0, -_NUDGE_DEG), (0.0, _NUDGE_DEG), (-_NUDGE_DEG, 0.0))
_NUDGE_SLEEP_S = 0.3


def _next_weekday_0830() -> str:
    """ISO 8601 datetime for the next weekday at 08:30 UTC."""
    target = datetime.now(UTC).replace(hour=8, minute=30, second=0, microsecond=0)
    if target <= datetime.now(UTC):
        target += timedelta(days=1)
    while target.weekday() >= 5:  # noqa: PLR2004
        target += timedelta(days=1)
    return target.isoformat()


class TransitousCommuteClient:
    """Concrete CommuteClient backed by the Transitous public API."""

    def journey_mins(self, from_lat: float, from_lng: float, to_lat: float, to_lng: float) -> int | None:
        mins = self._plan(from_lat, from_lng, to_lat, to_lng)
        if mins is None:
            return None  # transient failure — retry next run
        if mins != NO_JOURNEY:
            return mins

        # No itineraries from the exact origin: try nudged origins to recover
        # coordinates MOTIS can't snap to its network.
        saw_transient = False
        for dlat, dlng in _NUDGE_OFFSETS:
            time.sleep(_NUDGE_SLEEP_S)
            nudged = self._plan(from_lat + dlat, from_lng + dlng, to_lat, to_lng)
            if nudged is None:
                saw_transient = True
            elif nudged != NO_JOURNEY:
                log.info(
                    "Transitous: recovered %s,%s via nudged origin (%+.4f,%+.4f)",
                    from_lat,
                    from_lng,
                    dlat,
                    dlng,
                )
                return nudged

        if saw_transient:
            # A nudge hit a network error — inconclusive. Return None so the
            # whole pair is retried next run rather than committing a sentinel.
            return None
        log.info("Transitous: no route from %s,%s (or nudged) to %s,%s", from_lat, from_lng, to_lat, to_lng)
        return NO_JOURNEY

    def _plan(self, from_lat: float, from_lng: float, to_lat: float, to_lng: float) -> int | None:
        """Query Transitous once.

        Returns minutes (int >= 0) for a route, NO_JOURNEY (-1) when the API
        returns zero itineraries, or None on a transient HTTP/network error.
        """
        try:
            resp = requests.get(
                TRANSITOUS_API,
                params={
                    "fromPlace": f"{from_lat},{from_lng}",
                    "toPlace": f"{to_lat},{to_lng}",
                    "arriveBy": "true",
                    "time": _next_weekday_0830(),
                },
                headers={"User-Agent": USER_AGENT},
                timeout=15,
            )
            resp.raise_for_status()
            itineraries = resp.json().get("itineraries", [])
            if not itineraries:
                return NO_JOURNEY
            return min(it["duration"] for it in itineraries) // 60
        except requests.HTTPError:
            log.warning("Transitous HTTP error for %s,%s -> %s,%s", from_lat, from_lng, to_lat, to_lng, exc_info=True)
            return None
        except requests.RequestException:
            log.warning("Transitous request failed", exc_info=True)
            return None
