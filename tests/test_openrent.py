"""Tests for OpenRent search URL construction."""

import pytest
from flat_finder.scraper.openrent import build_search_url, snap_radius
from tests.conftest import params_of


class TestSnapRadius:
    """Feature: coerce a zone's covering radius to OpenRent's `within` granularity"""

    @pytest.mark.parametrize(
        ("requested", "expected"),
        [
            (0, 1),
            (0.79, 1),
            (1, 1),
            (1.38, 2),
            (1.83, 2),
            (2.42, 3),
            (3.51, 4),
            (4.1, 5),
            (10, 10),
        ],
    )
    def test_rounds_up_to_whole_km(self, requested: float, expected: int):
        """Given a covering radius in km
        When it is snapped
        Then the smallest whole km that still covers it is returned.
        """
        assert snap_radius(requested) == expected


class TestBuildSearchUrl:
    """Feature: assemble the OpenRent search URL"""

    def test_snaps_fractional_radius(self):
        """Given a radius derived from a zone polygon
        When the search URL is built
        Then `within` is rounded up to whole km rather than truncated.
        """
        assert params_of(build_search_url("Brighton", 1.83, 1, 3, 2200))["within"] == ["2"]

    def test_preserves_other_params(self):
        """Given search criteria
        When the search URL is built
        Then every other query parameter is carried through unchanged.
        """
        params = params_of(build_search_url("Brighton", 2.0, 1, 3, 2200))
        assert params["term"] == ["Brighton"]
        assert params["prices_min"] == ["0"]
        assert params["prices_max"] == ["2200"]
        assert params["bedrooms_min"] == ["1"]
        assert params["bedrooms_max"] == ["3"]
        assert params["isLive"] == ["true"]
