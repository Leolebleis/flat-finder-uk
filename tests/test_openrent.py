from scraper.openrent import build_search_url, parse_openrent_html

# Minimal fixture mimicking real OpenRent search results page structure.
# Includes two normal listings, one shared house (should be excluded),
# and one studio (should be excluded).  Also includes the JavaScript
# arrays that carry lat/lng and property-id data.
FIXTURE_HTML = """
<html>
<body>

<a href="/property-to-rent/london/1-bed-flat-goldhurst-terrace-nw6/2746356"
   class="pli search-property-card text-decoration-none" id="p0" m_n="0" sortorder="0">
    <div class="card overflow-hidden">
        <div class="grid gap-0">
            <div class="g-col-12 g-col-md-4 g-col-lg-3 rounded-start position-relative">
                <div class="property-row-carousel swiper z-10" data-listing-id="2746356" data-loaded="false">
                    <div class="swiper-wrapper">
                        <div class="swiper-slide w-100 h-100">
                            <img class="propertyPic w-100 h-100 object-fit-cover d-block"
                                 src="//imagescdn.openrent.co.uk/listings/2746356/photo.JPG"
                                 alt="1 Bed Flat, Goldhurst Terrace, NW6" />
                        </div>
                    </div>
                </div>
            </div>
            <div class="g-col-12 g-col-md-8 g-col-lg-9 card-body d-flex flex-column gap-2 fs-body-small-1">
                <div class="d-flex align-items-center gap-4 flex-wrap">
                    <div class="pim d-flex align-items-baseline gap-1"
                         x-show="!filters.useWeeklyPrices">
                        <span class="fs-4 fw-medium text-primary">&#xA3;2,100</span>
                        <span class="text-body-secondary">per month</span>
                    </div>
                </div>
                <div class="fw-medium text-primary fs-3">1 Bed Flat, Goldhurst Terrace, NW6</div>
                <div class="grid d-none d-md-grid">
                    <div class="g-col-12 g-col-lg-10 line-clamp-2">
                        ALL BILLS INCLUDED!!! Charming first floor flat with washing machine and balcony ...
                    </div>
                </div>
                <div class="d-flex gap-4 justify-content-between align-items-end mt-auto">
                    <ul class="list-unstyled d-flex flex-wrap fs-body-small-2 fw-medium mb-0 inline-list-divide">
                        <li>1 Bed</li>
                        <li>1 Bath</li>
                        <li>Furnished</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</a>

<a href="/property-to-rent/london/2-bed-flat-akenside-road-nw3/2801910"
   class="pli search-property-card text-decoration-none" id="p1" m_n="1" sortorder="1">
    <div class="card overflow-hidden">
        <div class="grid gap-0">
            <div class="g-col-12 g-col-md-4 g-col-lg-3 rounded-start position-relative">
                <div class="property-row-carousel swiper z-10" data-listing-id="2801910" data-loaded="false">
                    <div class="swiper-wrapper">
                        <div class="swiper-slide w-100 h-100">
                            <img class="propertyPic or-lazy-image w-100 h-100 object-fit-cover d-block"
                                 src="//staticcdn.openrent.co.uk/images/NoImageImage4x3.png"
                                 data-src="//imagescdn.openrent.co.uk/listings/2801910/photo2.JPG"
                                 alt="2 Bed Flat, Akenside Road, NW3" />
                        </div>
                    </div>
                </div>
            </div>
            <div class="g-col-12 g-col-md-8 g-col-lg-9 card-body d-flex flex-column gap-2 fs-body-small-1">
                <div class="d-flex align-items-center gap-4 flex-wrap">
                    <div class="pim d-flex align-items-baseline gap-1"
                         x-show="!filters.useWeeklyPrices">
                        <span class="fs-4 fw-medium text-primary">&#xA3;1,800</span>
                        <span class="text-body-secondary">per month</span>
                    </div>
                </div>
                <div class="fw-medium text-primary fs-3">2 Bed Flat, Akenside Road, NW3</div>
                <div class="grid d-none d-md-grid">
                    <div class="g-col-12 g-col-lg-10 line-clamp-2">
                        Spacious two bedroom flat with dishwasher and garden. Close to transport links.
                    </div>
                </div>
                <div class="d-flex gap-4 justify-content-between align-items-end mt-auto">
                    <ul class="list-unstyled d-flex flex-wrap fs-body-small-2 fw-medium mb-0 inline-list-divide">
                        <li>2 Beds</li>
                        <li>1 Bath</li>
                        <li>Part Furnished</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</a>

<a href="/property-to-rent/london/room-in-a-shared-house-frognal-nw3/2754632"
   class="pli search-property-card text-decoration-none" id="p2" m_n="2" sortorder="2">
    <div class="card overflow-hidden">
        <div class="grid gap-0">
            <div class="g-col-12 g-col-md-4 g-col-lg-3 rounded-start position-relative">
                <div class="property-row-carousel swiper z-10" data-listing-id="2754632" data-loaded="false">
                    <div class="swiper-wrapper">
                        <div class="swiper-slide w-100 h-100">
                            <img class="propertyPic w-100 h-100 object-fit-cover d-block"
                                 src="//imagescdn.openrent.co.uk/listings/2754632/photo3.JPG"
                                 alt="Room in a Shared House, Frognal, NW3" />
                        </div>
                    </div>
                </div>
            </div>
            <div class="g-col-12 g-col-md-8 g-col-lg-9 card-body d-flex flex-column gap-2 fs-body-small-1">
                <div class="d-flex align-items-center gap-4 flex-wrap">
                    <div class="pim d-flex align-items-baseline gap-1"
                         x-show="!filters.useWeeklyPrices">
                        <span class="fs-4 fw-medium text-primary">&#xA3;1,117</span>
                        <span class="text-body-secondary">per month</span>
                    </div>
                </div>
                <div class="fw-medium text-primary fs-3">Room in a Shared House, Frognal, NW3</div>
                <div class="grid d-none d-md-grid">
                    <div class="g-col-12 g-col-lg-10 line-clamp-2">
                        Furnished rooms in Finchley Road near the stations.
                    </div>
                </div>
                <div class="d-flex gap-4 justify-content-between align-items-end mt-auto">
                    <ul class="list-unstyled d-flex flex-wrap fs-body-small-2 fw-medium mb-0 inline-list-divide">
                        <li>2 Rooms Available</li>
                        <li>2 Baths</li>
                        <li>Furnished</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</a>

<a href="/property-to-rent/london/studio-flat-london-nw6/2773160"
   class="pli search-property-card text-decoration-none" id="p3" m_n="3" sortorder="3">
    <div class="card overflow-hidden">
        <div class="grid gap-0">
            <div class="g-col-12 g-col-md-4 g-col-lg-3 rounded-start position-relative">
                <div class="property-row-carousel swiper z-10" data-listing-id="2773160" data-loaded="false">
                    <div class="swiper-wrapper">
                        <div class="swiper-slide w-100 h-100">
                            <img class="propertyPic w-100 h-100 object-fit-cover d-block"
                                 src="//imagescdn.openrent.co.uk/listings/2773160/photo4.JPG"
                                 alt="Studio Flat, London, NW6" />
                        </div>
                    </div>
                </div>
            </div>
            <div class="g-col-12 g-col-md-8 g-col-lg-9 card-body d-flex flex-column gap-2 fs-body-small-1">
                <div class="d-flex align-items-center gap-4 flex-wrap">
                    <div class="pim d-flex align-items-baseline gap-1"
                         x-show="!filters.useWeeklyPrices">
                        <span class="fs-4 fw-medium text-primary">&#xA3;1,350</span>
                        <span class="text-body-secondary">per month</span>
                    </div>
                </div>
                <div class="fw-medium text-primary fs-3">Studio Flat, London, NW6</div>
                <div class="grid d-none d-md-grid">
                    <div class="g-col-12 g-col-lg-10 line-clamp-2">
                        Cosy studio flat in great location.
                    </div>
                </div>
                <div class="d-flex gap-4 justify-content-between align-items-end mt-auto">
                    <ul class="list-unstyled d-flex flex-wrap fs-body-small-2 fw-medium mb-0 inline-list-divide">
                        <li>Studio</li>
                        <li>1 Bath</li>
                        <li>Furnished</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</a>

<script type="text/javascript">
    var PROPERTYIDS = [ 2746356,2801910,2754632,2773160, ];
    var PROPERTYLISTLATITUDES = [
51.544373,51.55126,51.549522,51.54595,    ];
    var PROPERTYLISTLONGITUDES = [
-0.1800825,-0.1754696,-0.1809641,-0.1802326,    ];
</script>

</body>
</html>
"""


def test_build_search_url_includes_all_parameters():
    url = build_search_url(
        location="Finchley Road Station",
        radius_km=1,
        min_beds=1,
        max_beds=2,
        max_price=2200,
    )
    assert "openrent.co.uk/properties-to-rent" in url
    assert "term=Finchley" in url
    assert "within=1" in url
    assert "prices_max=2200" in url
    assert "bedrooms_min=1" in url
    assert "bedrooms_max=2" in url
    assert "isLive=true" in url


def test_build_search_url_encodes_spaces():
    url = build_search_url(
        location="Finchley Road Station",
        radius_km=1,
        min_beds=1,
        max_beds=2,
        max_price=2200,
    )
    # Spaces should be encoded as + or %20
    assert "Finchley+Road+Station" in url or "Finchley%20Road%20Station" in url


def test_parse_openrent_html_extracts_listings():
    listings = parse_openrent_html(FIXTURE_HTML)
    # Should have only 2 listings: the shared house and studio get filtered out
    assert len(listings) == 2


def test_parse_openrent_html_correct_ids():
    listings = parse_openrent_html(FIXTURE_HTML)
    ids = [l["id"] for l in listings]
    assert "openrent_2746356" in ids
    assert "openrent_2801910" in ids


def test_parse_openrent_html_excludes_shared():
    listings = parse_openrent_html(FIXTURE_HTML)
    ids = [l["id"] for l in listings]
    assert "openrent_2754632" not in ids  # shared house


def test_parse_openrent_html_excludes_studio():
    listings = parse_openrent_html(FIXTURE_HTML)
    ids = [l["id"] for l in listings]
    assert "openrent_2773160" not in ids  # studio


def test_parse_openrent_html_listing_fields():
    listings = parse_openrent_html(FIXTURE_HTML)
    listing = next(l for l in listings if l["id"] == "openrent_2746356")
    assert listing["source"] == "openrent"
    assert listing["url"] == "https://www.openrent.co.uk/property-to-rent/london/1-bed-flat-goldhurst-terrace-nw6/2746356"
    assert listing["title"] == "1 Bed Flat, Goldhurst Terrace, NW6"
    assert listing["price_pcm"] == 2100
    assert listing["bedrooms"] == 1
    assert listing["address"] == "Goldhurst Terrace, NW6"
    assert listing["image_url"] == "https://imagescdn.openrent.co.uk/listings/2746356/photo.JPG"
    assert listing["first_seen"] is not None
    assert listing["furnishing"] == "Furnished"


def test_parse_openrent_html_second_listing_fields():
    listings = parse_openrent_html(FIXTURE_HTML)
    listing = next(l for l in listings if l["id"] == "openrent_2801910")
    assert listing["price_pcm"] == 1800
    assert listing["bedrooms"] == 2
    assert listing["address"] == "Akenside Road, NW3"
    assert listing["furnishing"] == "Part Furnished"


def test_parse_openrent_html_coordinates():
    listings = parse_openrent_html(FIXTURE_HTML)
    listing = next(l for l in listings if l["id"] == "openrent_2746356")
    assert listing["latitude"] == 51.544373
    assert listing["longitude"] == -0.1800825


def test_parse_openrent_html_description_flags():
    listings = parse_openrent_html(FIXTURE_HTML)
    # First listing has "washing machine" and "balcony"
    listing1 = next(l for l in listings if l["id"] == "openrent_2746356")
    assert listing1["has_washer"] == "yes"
    assert listing1["has_outdoor"] == "yes"
    assert "balcony" in listing1["outdoor_type"]
    assert listing1["has_dishwasher"] == "unknown"

    # Second listing has "dishwasher" and "garden"
    listing2 = next(l for l in listings if l["id"] == "openrent_2801910")
    assert listing2["has_dishwasher"] == "yes"
    assert listing2["has_outdoor"] == "yes"
    assert "garden" in listing2["outdoor_type"]


def test_parse_openrent_html_lazy_image():
    """When first img uses placeholder src and real URL is in data-src."""
    listings = parse_openrent_html(FIXTURE_HTML)
    listing = next(l for l in listings if l["id"] == "openrent_2801910")
    assert listing["image_url"] == "https://imagescdn.openrent.co.uk/listings/2801910/photo2.JPG"


def test_parse_openrent_html_defaults():
    """Fields that OpenRent search pages don't provide should have sensible defaults."""
    listings = parse_openrent_html(FIXTURE_HTML)
    listing = listings[0]
    assert listing["property_type"] is not None  # extracted from title
    assert listing["sqft"] is None
    assert listing["listing_date"] is None


def test_parse_openrent_html_no_bedsit():
    """Bedsit listings should be excluded."""
    html_with_bedsit = """
    <html><body>
    <a href="/property-to-rent/london/bedsit-london-nw6/9999999"
       class="pli search-property-card text-decoration-none" id="p0" m_n="0" sortorder="0">
        <div class="card overflow-hidden">
            <div class="grid gap-0">
                <div class="g-col-12 g-col-md-4 g-col-lg-3 rounded-start position-relative">
                    <div class="property-row-carousel swiper z-10" data-listing-id="9999999" data-loaded="false">
                        <div class="swiper-wrapper">
                            <div class="swiper-slide w-100 h-100">
                                <img class="propertyPic" src="//img.jpg" alt="Bedsit, London, NW6" />
                            </div>
                        </div>
                    </div>
                </div>
                <div class="g-col-12 g-col-md-8 g-col-lg-9 card-body d-flex flex-column gap-2 fs-body-small-1">
                    <div class="d-flex align-items-center gap-4 flex-wrap">
                        <div class="pim d-flex align-items-baseline gap-1" x-show="!filters.useWeeklyPrices">
                            <span class="fs-4 fw-medium text-primary">&#xA3;900</span>
                            <span class="text-body-secondary">per month</span>
                        </div>
                    </div>
                    <div class="fw-medium text-primary fs-3">Bedsit, London, NW6</div>
                    <div class="grid d-none d-md-grid">
                        <div class="g-col-12 g-col-lg-10 line-clamp-2">A cosy bedsit near shops.</div>
                    </div>
                    <div class="d-flex gap-4 justify-content-between align-items-end mt-auto">
                        <ul class="list-unstyled d-flex flex-wrap fs-body-small-2 fw-medium mb-0 inline-list-divide">
                            <li>1 Bed</li>
                            <li>1 Bath</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </a>
    <script type="text/javascript">
        var PROPERTYIDS = [ 9999999, ];
        var PROPERTYLISTLATITUDES = [ 51.54, ];
        var PROPERTYLISTLONGITUDES = [ -0.18, ];
    </script>
    </body></html>
    """
    listings = parse_openrent_html(html_with_bedsit)
    assert len(listings) == 0
