from dataclasses import dataclass


@dataclass(frozen=True)
class Listing:
    id: str
    source: str
    url: str
    title: str | None
    price_pcm: int | None
    bedrooms: int | None
    address: str | None
    latitude: float | None
    longitude: float | None
    description: str | None
    image_url: str | None
    property_type: str | None
    furnishing: str | None
    sqft: int | None
    has_dishwasher: str
    has_washer: str
    has_outdoor: str
    outdoor_type: str | None
    zone: str | None
    first_seen: str
    listing_date: str | None


@dataclass(frozen=True)
class ListingState:
    user_id: int
    listing_id: str
    seen: bool
    favourite: bool
    notes: str | None
    override_dishwasher: str | None
    override_washer: str | None
    override_outdoor: str | None
    updated_at: str | None
