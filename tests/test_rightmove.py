from scraper.rightmove import parse_rightmove_response, build_search_url

def test_build_search_url_includes_parameters():
    url = build_search_url(
        location_id="REGION^61294",
        radius=1.0,
        min_beds=1,
        max_beds=2,
        max_price=2200,
    )
    assert "locationIdentifier=REGION%5E61294" in url or "locationIdentifier=REGION^61294" in url
    assert "radius=1.0" in url
    assert "minBedrooms=1" in url
    assert "maxBedrooms=2" in url
    assert "maxPrice=2200" in url
    assert "channel=RENT" in url

def test_parse_rightmove_response_extracts_listings():
    sample_response = {
        "properties": [
            {
                "id": 12345,
                "propertyTypeFullDescription": "2 bedroom flat",
                "displayAddress": "Swiss Cottage, NW6",
                "price": {"amount": 1800, "frequency": "monthly"},
                "bedrooms": 2,
                "propertyImages": {"images": [{"srcUrl": "https://example.com/img.jpg"}]},
                "location": {"latitude": 51.543, "longitude": -0.175},
                "propertyUrl": "/properties/12345",
                "summary": "Lovely 2 bed flat with dishwasher and balcony",
                "displaySize": "750 sq. ft.",
                "formattedBranchName": "Some Agent",
                "lettingInformation": {"furnishType": "Furnished"},
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
                "lettingInformation": {"furnishType": "Furnished"},
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
                "lettingInformation": {"furnishType": "Furnished"},
            },
        ]
    }
    listings = parse_rightmove_response(sample_response)
    assert len(listings) == 1
    assert listings[0]["id"] == "rightmove_2"
