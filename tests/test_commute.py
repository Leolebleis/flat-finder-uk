from unittest.mock import patch, MagicMock
from scraper.commute import get_commute_mins

def test_get_commute_mins_returns_shortest():
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
        result = get_commute_mins(51.5472, -0.1803)
    assert result == 32
    # Verify TfL API was called with correct params
    call_url = mock_get.call_args[0][0]
    assert "51.5472,-0.1803" in call_url
    assert "51.4875,-0.1827" in call_url

def test_get_commute_mins_returns_none_on_error():
    with patch("scraper.commute.requests.get", side_effect=Exception("timeout")):
        result = get_commute_mins(51.5472, -0.1803)
    assert result is None

def test_get_commute_mins_returns_none_for_no_journeys():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"journeys": []}
    with patch("scraper.commute.requests.get", return_value=mock_resp):
        result = get_commute_mins(51.5472, -0.1803)
    assert result is None
