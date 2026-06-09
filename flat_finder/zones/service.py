import logging

from flat_finder.zones.dao import ZoneDAO
from flat_finder.zones.model import Zone

log = logging.getLogger(__name__)

POI_COLORS = [
    {"name": "blue", "color": "#1d4ed8", "bg": "#dbeafe", "dark_color": "#93c5fd", "dark_bg": "#172554"},
    {"name": "orange", "color": "#c2410c", "bg": "#ffedd5", "dark_color": "#fdba74", "dark_bg": "#431407"},
    {"name": "purple", "color": "#7c3aed", "bg": "#ede9fe", "dark_color": "#c4b5fd", "dark_bg": "#2e1065"},
    {"name": "teal", "color": "#0f766e", "bg": "#ccfbf1", "dark_color": "#2dd4bf", "dark_bg": "#042f2e"},
    {"name": "rose", "color": "#be123c", "bg": "#ffe4e6", "dark_color": "#fda4af", "dark_bg": "#4c0519"},
    {"name": "amber", "color": "#b45309", "bg": "#fef3c7", "dark_color": "#fcd34d", "dark_bg": "#451a03"},
    {"name": "emerald", "color": "#047857", "bg": "#d1fae5", "dark_color": "#34d399", "dark_bg": "#064e3b"},
    {"name": "slate", "color": "#475569", "bg": "#f1f5f9", "dark_color": "#94a3b8", "dark_bg": "#1e293b"},
]


def _zone_to_dict(zone: Zone, colors: list[dict]) -> dict:
    return {
        "id": zone.id,
        "user_id": zone.user_id,
        "name": zone.name,
        "geometry": zone.geometry,
        "centroid_lat": zone.centroid_lat,
        "centroid_lng": zone.centroid_lng,
        "covering_radius_km": zone.covering_radius_km,
        "rightmove_id": zone.rightmove_id,
        "openrent_term": zone.openrent_term,
        "color_index": zone.color_index,
        "created_at": zone.created_at,
        "color": colors[zone.color_index % len(colors)],
    }


class ZoneService:
    POI_COLORS = POI_COLORS

    def __init__(self, zone_dao: ZoneDAO) -> None:
        self._dao = zone_dao

    def get_user_zones(self, user_id: int) -> list[dict]:
        """Get user's zones with color info attached."""
        zones = self._dao.get_by_user(user_id)
        return [self._with_color(z) for z in zones]

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
        color_index = len(existing) % len(self.POI_COLORS)
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
        return self._with_color(zone)

    def delete_zone(self, user_id: int, zone_id: int) -> bool:
        """Delete zone if it belongs to user. Returns True if deleted."""
        zone = self._dao.get_by_id(zone_id)
        if not zone or zone.user_id != user_id:
            return False
        self._dao.delete(zone_id)
        log.info("Deleted zone %d for user %d", zone_id, user_id)
        return True

    def update_zone(self, user_id: int, zone_id: int, **kwargs: object) -> bool:
        """Update zone fields if it belongs to user. Returns True if updated."""
        zone = self._dao.get_by_id(zone_id)
        if not zone or zone.user_id != user_id:
            return False
        self._dao.update(zone_id, **kwargs)
        log.info("Updated zone %d for user %d", zone_id, user_id)
        return True

    def _with_color(self, zone: Zone) -> dict:
        return _zone_to_dict(zone, self.POI_COLORS)
