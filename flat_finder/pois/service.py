import logging
from dataclasses import asdict

from flat_finder.colors import POI_COLORS, color_for
from flat_finder.pois.dao import POIDAO, POICommuteDAO
from flat_finder.pois.model import POI

log = logging.getLogger(__name__)


def _poi_to_dict(poi: POI) -> dict:
    return {**asdict(poi), "color": color_for(poi.color_index)}


class POIService:
    def __init__(self, poi_dao: POIDAO, commute_dao: POICommuteDAO) -> None:
        self._dao = poi_dao
        self._commute_dao = commute_dao

    def get_user_pois(self, user_id: int) -> list[dict]:
        """Get user's POIs with color info attached."""
        pois = self._dao.get_by_user(user_id)
        return [_poi_to_dict(p) for p in pois]

    def add_poi(self, user_id: int, name: str, lat: float, lng: float) -> dict:
        """Add a POI for a user, auto-assigning color_index."""
        existing = self._dao.get_by_user(user_id)
        color_index = len(existing) % len(POI_COLORS)
        poi = self._dao.create(user_id, name, lat, lng, color_index)
        log.info("Created POI %d (%s) for user %d", poi.id, poi.name, user_id)
        return _poi_to_dict(poi)

    def delete_poi(self, user_id: int, poi_id: int) -> bool:
        """Delete POI if it belongs to user, cascade-deleting commutes. Returns True if deleted."""
        poi = self._dao.get_by_id(poi_id)
        if not poi or poi.user_id != user_id:
            return False
        self._dao.delete(poi_id)
        log.info("Deleted POI %d for user %d (commutes cascade-deleted)", poi_id, user_id)
        return True
