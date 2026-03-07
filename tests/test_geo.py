from shared.geo import extract_coords_from_url


def test_extract_coords_from_full_url():
    url = "https://www.google.com/maps/@51.5497263,-0.1782744,2693m/data=!3m1!1e3"
    lat, lng = extract_coords_from_url(url)
    assert abs(lat - 51.5497263) < 0.0001
    assert abs(lng - (-0.1782744)) < 0.0001


def test_extract_coords_from_place_url():
    url = "https://www.google.com/maps/place/Anytime+Fitness/@51.5445,-0.1762,17z/"
    lat, lng = extract_coords_from_url(url)
    assert abs(lat - 51.5445) < 0.0001
    assert abs(lng - (-0.1762)) < 0.0001


def test_extract_coords_returns_none_for_garbage():
    assert extract_coords_from_url("not a url") is None
    assert extract_coords_from_url("https://google.com") is None


def test_extract_coords_from_query_param():
    url = "https://www.google.com/maps?q=51.5445,-0.1762"
    lat, lng = extract_coords_from_url(url)
    assert abs(lat - 51.5445) < 0.0001
    assert abs(lng - (-0.1762)) < 0.0001
