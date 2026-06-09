import logging

from flat_finder.pois.dao import POIDAO, POICommuteDAO
from flat_finder.pois.model import POI
from flat_finder.zones.service import POI_COLORS

log = logging.getLogger(__name__)


def _poi_to_dict(poi: POI, colors: list[dict]) -> dict:
    return {
        "id": poi.id,
        "user_id": poi.user_id,
        "name": poi.name,
        "lat": poi.lat,
        "lng": poi.lng,
        "color_index": poi.color_index,
        "created_at": poi.created_at,
        "color": colors[poi.color_index % len(colors)],
    }


class POIService:
    POI_COLORS = POI_COLORS

    def __init__(self, poi_dao: POIDAO, commute_dao: POICommuteDAO) -> None:
        self._dao = poi_dao
        self._commute_dao = commute_dao

    def get_user_pois(self, user_id: int) -> list[dict]:
        """Get user's POIs with color info attached."""
        pois = self._dao.get_by_user(user_id)
        return [self._with_color(p) for p in pois]

    def add_poi(self, user_id: int, name: str, lat: float, lng: float) -> dict:
        """Add a POI for a user, auto-assigning color_index."""
        existing = self._dao.get_by_user(user_id)
        color_index = len(existing) % len(self.POI_COLORS)
        poi = self._dao.create(user_id, name, lat, lng, color_index)
        log.info("Created POI %d (%s) for user %d", poi.id, poi.name, user_id)
        return self._with_color(poi)

    def delete_poi(self, user_id: int, poi_id: int) -> bool:
        """Delete POI if it belongs to user, cascade-deleting commutes. Returns True if deleted."""
        pois = self._dao.get_by_user(user_id)
        owned_ids = {p.id for p in pois}
        if poi_id not in owned_ids:
            return False
        self._dao.delete(poi_id)
        log.info("Deleted POI %d for user %d (commutes cascade-deleted)", poi_id, user_id)
        return True

    def _with_color(self, poi: POI) -> dict:
        return _poi_to_dict(poi, self.POI_COLORS)
