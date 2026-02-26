import logging
import requests

log = logging.getLogger("flat-finder")

DESTINATION_LAT = 51.4869
DESTINATION_LNG = -0.1832
TFL_MODES = "tube,bus,overground,elizabeth-line,dlr,tram"

def get_commute_mins(lat: float, lng: float) -> int | None:
    url = f"https://api.tfl.gov.uk/Journey/JourneyResults/{lat},{lng}/to/{DESTINATION_LAT},{DESTINATION_LNG}"
    try:
        resp = requests.get(url, params={
            "mode": TFL_MODES,
            "time": "0830",
            "timeIs": "arriving",
        }, timeout=15)
        resp.raise_for_status()
        journeys = resp.json().get("journeys", [])
        if not journeys:
            return None
        return min(j["duration"] for j in journeys)
    except Exception as e:
        log.error(f"TfL commute lookup failed: {e}")
        return None
