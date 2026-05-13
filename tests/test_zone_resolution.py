import json
from unittest.mock import MagicMock, patch

import pytest
from shared.zones import (
    compute_zone_params,
    point_in_zone,
    resolve_postcode,
    resolve_rightmove_id,
)

SQUARE_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[-0.19, 51.54], [-0.17, 51.54], [-0.17, 51.56], [-0.19, 51.56], [-0.19, 51.54]]],
}


def test_compute_zone_params_centroid():
    params = compute_zone_params(SQUARE_POLYGON)
    assert abs(params["centroid_lat"] - 51.55) < 0.01
    assert abs(params["centroid_lng"] - (-0.18)) < 0.01


def test_compute_zone_params_covering_radius():
    params = compute_zone_params(SQUARE_POLYGON)
    assert params["covering_radius_km"] > 0
    assert params["covering_radius_km"] < 3.0


def test_compute_zone_params_validates_polygon():
    with pytest.raises(ValueError, match="Expected Polygon"):
        compute_zone_params({"type": "Point", "coordinates": [0, 0]})


def test_point_in_polygon_inside():
    geom_str = json.dumps(SQUARE_POLYGON)
    assert point_in_zone(51.55, -0.18, geom_str) is True


def test_point_in_polygon_outside():
    geom_str = json.dumps(SQUARE_POLYGON)
    assert point_in_zone(52.0, -0.18, geom_str) is False


@patch("shared.zones.requests.get")
def test_resolve_postcode(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": 200, "result": [{"outcode": "NW6", "postcode": "NW6 1NB"}]}
    mock_get.return_value = mock_resp
    result = resolve_postcode(51.545, -0.18)
    assert result == "NW6"


@patch("shared.zones.requests.get")
def test_resolve_postcode_returns_none_on_failure(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": 200, "result": []}
    mock_get.return_value = mock_resp
    result = resolve_postcode(51.545, -0.18)
    assert result is None


@patch("shared.zones.requests.get")
def test_resolve_rightmove_id(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"matches": [{"id": "1862", "type": "OUTCODE", "displayName": "NW6"}]}
    mock_get.return_value = mock_resp
    result = resolve_rightmove_id("NW6")
    assert result == "OUTCODE^1862"


@patch("shared.zones.requests.get")
def test_resolve_rightmove_id_returns_none_on_empty(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"matches": []}
    mock_get.return_value = mock_resp
    result = resolve_rightmove_id("ZZZZZ")
    assert result is None
