import logging
import requests

log = logging.getLogger("flat-finder")

TFL_MODES = "tube,bus,overground,elizabeth-line,dlr,tram"


def tfl_journey_mins(from_lat: float, from_lng: float,
                     to_lat: float, to_lng: float,
                     arrive_by: str = "0830") -> int | None:
    """Query TfL Journey Planner for shortest journey duration in minutes."""
    url = f"https://api.tfl.gov.uk/Journey/JourneyResults/{from_lat},{from_lng}/to/{to_lat},{to_lng}"
    try:
        resp = requests.get(url, params={
            "mode": TFL_MODES,
            "time": arrive_by,
            "timeIs": "arriving",
        }, timeout=15)
        resp.raise_for_status()
        journeys = resp.json().get("journeys", [])
        if not journeys:
            return None
        return min(j["duration"] for j in journeys)
    except Exception as e:
        log.error(f"TfL journey lookup failed: {e}")
        return None
