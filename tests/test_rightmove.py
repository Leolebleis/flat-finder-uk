from scraper.rightmove import parse_rightmove_response, build_search_url, _extract_next_data, _check_description

def test_build_search_url_includes_parameters():
    url = build_search_url(
        location_id="STATION^3509",
        radius=1.0,
        min_beds=1,
        max_beds=2,
        max_price=2200,
    )
    assert "locationIdentifier=STATION%5E3509" in url or "locationIdentifier=STATION^3509" in url
    assert "radius=1.0" in url
    assert "minBedrooms=1" in url
    assert "maxBedrooms=2" in url
    assert "maxPrice=2200" in url
    assert "channel=RENT" in url
    assert "property-to-rent/find.html" in url

def test_parse_rightmove_response_extracts_listings():
    sample_response = {
        "properties": [
            {
                "id": 12345,
                "propertyTypeFullDescription": "2 bedroom flat",
                "propertySubType": "Flat",
                "displayAddress": "Swiss Cottage, NW6",
                "price": {"amount": 1800, "frequency": "monthly"},
                "bedrooms": 2,
                "propertyImages": {"images": [{"srcUrl": "https://example.com/img.jpg"}]},
                "location": {"latitude": 51.543, "longitude": -0.175},
                "propertyUrl": "/properties/12345",
                "summary": "Lovely 2 bed furnished flat with dishwasher and balcony",
                "displaySize": "750 sq. ft.",
                "formattedBranchName": "Some Agent",
                "firstVisibleDate": "2026-02-26T00:00:00Z",
            }
        ]
    }
    listings = parse_rightmove_response(sample_response)
    assert len(listings) == 1
    listing = listings[0]
    assert listing["id"] == "rightmove_12345"
    assert listing["source"] == "rightmove"
    assert listing["price_pcm"] == 1800
    assert listing["bedrooms"] == 2
    assert listing["address"] == "Swiss Cottage, NW6"
    assert listing["latitude"] == 51.543
    assert listing["has_dishwasher"] == "yes"
    assert listing["has_outdoor"] == "yes"
    assert listing["outdoor_type"] == "balcony"
    assert listing["furnishing"] == "Furnished"
    assert listing["sqft"] == 750
    assert listing["property_type"] == "Flat"

def test_parse_rightmove_filters_excluded_terms():
    sample_response = {
        "properties": [
            {
                "id": 1,
                "propertyTypeFullDescription": "Studio flat",
                "displayAddress": "NW6",
                "price": {"amount": 1200, "frequency": "monthly"},
                "bedrooms": 0,
                "propertyImages": {"images": []},
                "location": {"latitude": 51.54, "longitude": -0.17},
                "propertyUrl": "/properties/1",
                "summary": "Cosy studio",
            },
            {
                "id": 2,
                "propertyTypeFullDescription": "1 bedroom flat",
                "displayAddress": "NW6",
                "price": {"amount": 1500, "frequency": "monthly"},
                "bedrooms": 1,
                "propertyImages": {"images": []},
                "location": {"latitude": 51.54, "longitude": -0.17},
                "propertyUrl": "/properties/2",
                "summary": "Nice flat",
            },
        ]
    }
    listings = parse_rightmove_response(sample_response)
    assert len(listings) == 1
    assert listings[0]["id"] == "rightmove_2"

def test_parse_rightmove_weekly_price_conversion():
    sample_response = {
        "properties": [
            {
                "id": 99,
                "propertyTypeFullDescription": "1 bedroom flat",
                "displayAddress": "NW3",
                "price": {"amount": 390, "frequency": "weekly"},
                "bedrooms": 1,
                "propertyImages": {"images": []},
                "location": {"latitude": 51.54, "longitude": -0.17},
                "propertyUrl": "/properties/99",
                "summary": "Nice flat",
            }
        ]
    }
    listings = parse_rightmove_response(sample_response)
    assert len(listings) == 1
    # 390 * 52 / 12 = 1690
    assert listings[0]["price_pcm"] == 1690

def test_parse_rightmove_furnishing_from_description():
    sample_response = {
        "properties": [
            {
                "id": 100,
                "propertyTypeFullDescription": "1 bedroom flat",
                "displayAddress": "NW6",
                "price": {"amount": 1500, "frequency": "monthly"},
                "bedrooms": 1,
                "propertyImages": {"images": []},
                "location": {"latitude": 51.54, "longitude": -0.17},
                "propertyUrl": "/properties/100",
                "summary": "A lovely part-furnished flat in NW6",
            }
        ]
    }
    listings = parse_rightmove_response(sample_response)
    assert listings[0]["furnishing"] == "Part furnished"

def test_extract_next_data():
    html = '<html><script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"searchResults":{"resultCount":"5","properties":[]}}}}</script></html>'
    data = _extract_next_data(html)
    assert data["props"]["pageProps"]["searchResults"]["resultCount"] == "5"

def test_extract_next_data_raises_on_missing():
    import pytest
    with pytest.raises(ValueError, match="Could not find __NEXT_DATA__"):
        _extract_next_data("<html><body>No data here</body></html>")

def test_check_description_communal_garden_not_flagged():
    result = _check_description("Lovely flat with communal garden and modern kitchen")
    assert result["has_outdoor"] == "unknown"

def test_check_description_shared_garden_not_flagged():
    result = _check_description("1 bed flat with shared garden near station")
    assert result["has_outdoor"] == "unknown"

def test_check_description_street_name_gardens_not_flagged():
    result = _check_description("Located on Maida Vale Gardens, close to shops")
    assert result["has_outdoor"] == "unknown"

def test_check_description_private_garden_flagged():
    result = _check_description("Beautiful flat with private garden")
    assert result["has_outdoor"] == "yes"
    assert "garden" in result["outdoor_type"]

def test_check_description_just_garden_flagged():
    result = _check_description("Spacious flat with garden and parking")
    assert result["has_outdoor"] == "yes"
    assert "garden" in result["outdoor_type"]

def test_check_description_balcony_still_works():
    result = _check_description("Modern flat with balcony overlooking park")
    assert result["has_outdoor"] == "yes"
    assert "balcony" in result["outdoor_type"]
