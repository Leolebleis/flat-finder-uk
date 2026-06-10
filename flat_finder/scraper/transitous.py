"""Transitous API client — UK-wide public transit commute times.

Transitous is a community-run routing service (transitous.org) backed by MOTIS,
covering all of Great Britain (buses, rail, tube, coach). Replaces TfL Journey
Planner which only covers the London bounding box.
"""

import logging
from datetime import UTC, datetime, timedelta

import requests

from flat_finder.scraper.commute import NO_JOURNEY

log = logging.getLogger("flat-finder")

TRANSITOUS_API = "https://api.transitous.org/api/v6/plan"
USER_AGENT = "flat-finder/1.0 (leo.lebleis@gmail.com)"


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
                log.info(
                    "Transitous: no itineraries from %s,%s to %s,%s",
                    from_lat,
                    from_lng,
                    to_lat,
                    to_lng,
                )
                return NO_JOURNEY
            return min(it["duration"] for it in itineraries) // 60
        except requests.HTTPError:
            log.warning(
                "Transitous HTTP error for %s,%s -> %s,%s",
                from_lat,
                from_lng,
                to_lat,
                to_lng,
                exc_info=True,
            )
            return None
        except requests.RequestException:
            log.warning("Transitous request failed", exc_info=True)
            return None
