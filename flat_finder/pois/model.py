from dataclasses import dataclass


@dataclass(frozen=True)
class POI:
    id: int
    user_id: int
    name: str
    lat: float
    lng: float
    color_index: int
    created_at: str
