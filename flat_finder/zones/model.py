from dataclasses import dataclass


@dataclass(frozen=True)
class Zone:
    id: int
    user_id: int
    name: str
    geometry: str
    centroid_lat: float
    centroid_lng: float
    covering_radius_km: float
    rightmove_id: str | None
    openrent_term: str | None
    color_index: int
    created_at: str
