from unittest.mock import MagicMock, patch

from scraper.commute import tfl_journey_mins


def test_tfl_journey_mins_returns_shortest():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "journeys": [
            {"duration": 45},
            {"duration": 32},
            {"duration": 50},
        ]
    }
    with patch("scraper.commute.requests.get", return_value=mock_resp) as mock_get:
        result = tfl_journey_mins(51.5472, -0.1803, 51.4869, -0.1832)
    assert result == 32
    call_url = mock_get.call_args[0][0]
    assert "51.5472,-0.1803" in call_url
    assert "51.4869,-0.1832" in call_url


def test_tfl_journey_mins_returns_none_on_error():
    with patch("scraper.commute.requests.get", side_effect=Exception("timeout")):
        result = tfl_journey_mins(51.5472, -0.1803, 51.4869, -0.1832)
    assert result is None


def test_tfl_journey_mins_returns_none_for_no_journeys():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"journeys": []}
    with patch("scraper.commute.requests.get", return_value=mock_resp):
        result = tfl_journey_mins(51.5472, -0.1803, 51.4869, -0.1832)
    assert result is None
