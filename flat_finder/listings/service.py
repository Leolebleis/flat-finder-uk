import logging
from dataclasses import asdict
from typing import Any

from flat_finder.listings.dao import ListingDAO, ListingStateDAO
from flat_finder.pois.dao import POICommuteDAO

log = logging.getLogger(__name__)

SORT_OPTIONS = {
    "best_match": "Best match",
    "newest": "Newest first",
    "price_asc": "Price (low to high)",
    "price_desc": "Price (high to low)",
    "size_desc": "Size (largest)",
    "commute": "Commute (shortest)",
}

_OVERRIDE_FIELDS = (
    ("override_dishwasher", "has_dishwasher"),
    ("override_washer", "has_washer"),
    ("override_outdoor", "has_outdoor"),
)


def _apply_overrides(d: dict[str, Any]) -> None:
    """Apply user_state override_* values onto the live has_* fields, in place."""
    for override_key, target_key in _OVERRIDE_FIELDS:
        if d.get(override_key):
            d[target_key] = d[override_key]


def _normalize_listing(d: dict[str, Any]) -> dict[str, Any]:
    """Normalize a listing dict into the shape templates/API consumers expect."""
    result = dict(d)
    result["seen"] = bool(result["seen"]) if result["seen"] else False
    result["favourite"] = bool(result["favourite"]) if result["favourite"] else False
    _apply_overrides(result)
    return result


def _min_commute(listing: dict[str, Any]) -> int | None:
    """Shortest commute across all of this listing's POIs, or None if no data."""
    commutes = listing.get("poi_commutes") or {}
    return min(commutes.values()) if commutes else None


def _compute_scores(
    listings: list[dict[str, Any]],
    poi_ids: list[int],
    weights: dict[int, float] | None = None,
) -> None:
    """Compute weighted match scores in-place using dynamic POIs."""
    if not poi_ids:
        for listing in listings:
            listing["match_score"] = None
        return

    if weights is None:
        w = 1.0 / len(poi_ids)
        weights = dict.fromkeys(poi_ids, w)

    total = sum(weights.values())
    if total > 0:
        weights = {k: v / total for k, v in weights.items()}

    stats: dict[int, dict[str, float]] = {}
    for pid in poi_ids:
        vals = [listing["poi_commutes"][pid] for listing in listings if pid in listing.get("poi_commutes", {})]
        if vals:
            mn, mx = min(vals), max(vals)
            stats[pid] = {"min": mn, "max": mx, "range": mx - mn if mx != mn else 1}

    for listing in listings:
        total_score = 0.0
        for pid in poi_ids:
            if pid in stats and pid in listing.get("poi_commutes", {}):
                s = stats[pid]
                val = listing["poi_commutes"][pid]
                total_score += weights.get(pid, 0) * 100 * (1 - (val - s["min"]) / s["range"])
        listing["match_score"] = round(total_score)


_SORT_KEYS: dict[str, Any] = {
    "best_match": lambda listing: -(listing.get("match_score") or 0),
    "price_asc": lambda listing: (listing["price_pcm"] is None, listing["price_pcm"] or 0),
    "price_desc": lambda listing: (listing["price_pcm"] is None, -(listing["price_pcm"] or 0)),
    "size_desc": lambda listing: (listing["sqft"] is None, -(listing["sqft"] or 0)),
    "commute": lambda listing: (_min_commute(listing) is None, _min_commute(listing) or 999),
}


def _sort_listings(listings: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
    key_fn = _SORT_KEYS.get(sort)
    if key_fn is None:
        return listings  # newest — already sorted by first_seen DESC from SQL
    return sorted(listings, key=key_fn)


class ListingService:
    def __init__(
        self,
        listing_dao: ListingDAO,
        state_dao: ListingStateDAO,
        commute_dao: POICommuteDAO,
    ) -> None:
        self._listing_dao = listing_dao
        self._state_dao = state_dao
        self._commute_dao = commute_dao

    def get_feed_data(
        self,
        user_id: int,
        zone_ids: list[int],
        pois: list[dict[str, Any]],
        sort: str = "newest",
    ) -> dict[str, Any]:
        """Build feed page context. Returns dict with listings, sort, zones, pois."""
        if sort not in SORT_OPTIONS:
            sort = "newest"

        raw_listings = self._listing_dao.get_all_with_state(user_id, zone_ids)
        listings = [_normalize_listing(r) for r in raw_listings]

        all_commutes = self._commute_dao.get_for_listings([lst["id"] for lst in listings])
        for listing in listings:
            listing["poi_commutes"] = all_commutes.get(listing["id"], {})

        poi_ids = [p["id"] for p in pois]
        _compute_scores(listings, poi_ids)
        listings = _sort_listings(listings, sort)

        return {
            "listings": listings,
            "sort": sort,
            "sort_options": SORT_OPTIONS,
            "pois": pois,
        }

    def get_detail_data(
        self,
        user_id: int,
        listing_id: str,
        pois: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Build detail page context. Returns None if listing not found."""
        listing_obj = self._listing_dao.get_by_id(listing_id)
        if listing_obj is None:
            return None

        state = self._state_dao.get(user_id, listing_id)

        listing: dict[str, Any] = asdict(listing_obj)
        listing.update(
            seen=bool(state.seen) if state else False,
            favourite=bool(state.favourite) if state else False,
            notes=state.notes if state else None,
            override_dishwasher=state.override_dishwasher if state else None,
            override_washer=state.override_washer if state else None,
            override_outdoor=state.override_outdoor if state else None,
        )

        # Stash originals before applying overrides — detail page surfaces both
        listing["original_dishwasher"] = listing["has_dishwasher"]
        listing["original_washer"] = listing["has_washer"]
        listing["original_outdoor"] = listing["has_outdoor"]
        _apply_overrides(listing)

        commutes_map = self._commute_dao.get_for_listings([listing_id])
        listing["poi_commutes"] = commutes_map.get(listing_id, {})

        return {"listing": listing, "pois": pois}

    def exists(self, listing_id: str) -> bool:
        """Check whether a listing exists."""
        return self._listing_dao.get_by_id(listing_id) is not None

    def update_state(
        self,
        user_id: int,
        listing_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Upsert user state for a listing. Returns the updated state as a dict."""
        return asdict(self._state_dao.upsert(user_id, listing_id, updates))
