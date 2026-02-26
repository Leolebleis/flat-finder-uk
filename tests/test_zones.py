import json
import tempfile
from pathlib import Path
from shared.config import load_zones

def test_load_zones_from_file():
    zones = [
        {"name": "Finchley Road", "rightmove_id": "STATION^3509",
         "openrent_term": "Finchley Road Station", "radius_miles": 1.0,
         "lat": 51.5472, "lng": -0.1803},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(zones, f)
        f.flush()
        result = load_zones(Path(f.name))
    assert len(result) == 1
    assert result[0]["name"] == "Finchley Road"
    assert result[0]["rightmove_id"] == "STATION^3509"

def test_load_zones_fallback_when_file_missing():
    result = load_zones(Path("/nonexistent/zones.json"))
    assert len(result) == 1
    assert result[0]["name"] == "Default"
