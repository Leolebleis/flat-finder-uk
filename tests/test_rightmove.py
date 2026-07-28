"""Tests for Rightmove search URL construction."""

import pytest
from flat_finder.scraper.rightmove import ALLOWED_RADII, build_search_url, snap_radius
from tests.conftest import params_of


class TestSnapRadius:
    """Feature: coerce a computed radius to one Rightmove will accept"""

    @pytest.mark.parametrize(
        ("requested", "expected"),
        [
            (0, 0.0),
            (0.1, 0.25),
            (0.25, 0.25),
            (0.5, 0.5),
            (0.8574943765767332, 1.0),
            (1, 1.0),
            (1.01, 3.0),
            (2.1810183056408214, 3.0),
            (3, 3.0),
            (12, 15.0),
            (40, 40.0),
        ],
    )
    def test_rounds_up_to_allowed_value(self, requested: float, expected: float):
        """Given a radius in miles
        When it is snapped
        Then the smallest allowed value that still covers it is returned.
        """
        assert snap_radius(requested) == expected

    def test_clamps_above_max(self):
        """Given a radius larger than Rightmove's widest search
        When it is snapped
        Then it clamps to 40 miles rather than falling through.
        """
        assert snap_radius(100) == 40.0

    def test_clamps_negative_to_min(self):
        """Given a nonsensical negative radius
        When it is snapped
        Then it clamps to 0 rather than producing a rejected value.
        """
        assert snap_radius(-5) == 0.0

    def test_never_shrinks_the_search_area(self):
        """Given any radius across Rightmove's supported range
        When it is snapped
        Then the result is never smaller than requested.

        Rounding to nearest would be wrong: the caller post-filters against the
        zone polygon, so over-fetch is discarded but under-fetch loses listings.
        """
        for step in range(0, 4000, 13):
            requested = step / 100
            assert snap_radius(requested) >= requested


class TestBuildSearchUrl:
    """Feature: assemble the Rightmove search URL"""

    def test_snaps_arbitrary_radius(self):
        """Given a radius derived from a zone polygon
        When the search URL is built
        Then the radius is snapped to an accepted value.

        Rightmove redirects any other radius to /page-not-found, whose HTML has
        no __NEXT_DATA__ blob — this silently broke every zone on 2026-07-20.
        """
        url = build_search_url("OUTCODE^1684", 2.1810183056408214, 1, 3, 2200)
        assert params_of(url)["radius"] == ["3.0"]

    def test_preserves_other_params(self):
        """Given search criteria and a pagination offset
        When the search URL is built
        Then every other query parameter is carried through unchanged.
        """
        params = params_of(build_search_url("OUTCODE^1684", 1.0, 1, 3, 2200, index=48))
        assert params["locationIdentifier"] == ["OUTCODE^1684"]
        assert params["minBedrooms"] == ["1"]
        assert params["maxBedrooms"] == ["3"]
        assert params["maxPrice"] == ["2200"]
        assert params["index"] == ["48"]
        assert params["channel"] == ["RENT"]

    def test_every_zone_radius_snaps_into_the_allowed_set(self):
        """Given the full range of plausible zone covering radii
        When search URLs are built
        Then the radius param is always a value Rightmove accepts.
        """
        for step in range(0, 4000, 37):
            radius = params_of(build_search_url("OUTCODE^1", step / 100, 1, 3, 2200))["radius"][0]
            assert float(radius) in ALLOWED_RADII
