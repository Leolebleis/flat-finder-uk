import logging
from dataclasses import asdict

from flat_finder.colors import POI_COLORS, color_for
from flat_finder.zones.dao import ZoneDAO
from flat_finder.zones.model import Zone

log = logging.getLogger(__name__)


def _zone_to_dict(zone: Zone) -> dict:
    return {**asdict(zone), "color": color_for(zone.color_index)}


class ZoneService:
    def __init__(self, zone_dao: ZoneDAO) -> None:
        self._dao = zone_dao

    def get_user_zones(self, user_id: int) -> list[dict]:
        """Get user's zones with color info attached."""
        zones = self._dao.get_by_user(user_id)
        return [_zone_to_dict(z) for z in zones]

    def create_zone(  # noqa: PLR0913
        self,
        user_id: int,
        name: str,
        geometry: str,
        centroid_lat: float,
        centroid_lng: float,
        covering_radius_km: float,
        rightmove_id: str | None,
        openrent_term: str | None,
    ) -> dict:
        """Create a zone for a user, auto-assigning color_index."""
        existing = self._dao.get_by_user(user_id)
        color_index = len(existing) % len(POI_COLORS)
        zone = self._dao.create(
            user_id,
            name,
            geometry,
            centroid_lat,
            centroid_lng,
            covering_radius_km,
            rightmove_id,
            openrent_term,
            color_index,
        )
        log.info("Created zone %d (%s) for user %d", zone.id, zone.name, user_id)
        return _zone_to_dict(zone)

    def delete_zone(self, user_id: int, zone_id: int) -> bool:
        """Delete zone if it belongs to user. Returns True if deleted."""
        zone = self._dao.get_by_id(zone_id)
        if not zone or zone.user_id != user_id:
            return False
        self._dao.delete(zone_id)
        log.info("Deleted zone %d for user %d", zone_id, user_id)
        return True

    def update_zone(self, user_id: int, zone_id: int, **kwargs: object) -> dict | None:
        """Update zone fields if it belongs to user. Returns the updated zone, or None."""
        zone = self._dao.get_by_id(zone_id)
        if not zone or zone.user_id != user_id:
            return None
        self._dao.update(zone_id, **kwargs)
        log.info("Updated zone %d for user %d", zone_id, user_id)
        updated = self._dao.get_by_id(zone_id)
        return _zone_to_dict(updated) if updated else None
