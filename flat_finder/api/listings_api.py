import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from flat_finder.api.dependencies import (
    get_current_user_id,
    get_listing_service,
    get_zone_service,
)
from flat_finder.listings.service import ListingService
from flat_finder.zones.service import ZoneService

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/listings")
def api_listings(
    user_id: Annotated[int, Depends(get_current_user_id)],
    listing_service: Annotated[ListingService, Depends(get_listing_service)],
    zone_service: Annotated[ZoneService, Depends(get_zone_service)],
) -> list[dict[str, Any]]:
    zones = zone_service.get_user_zones(user_id)
    zone_ids = [z["id"] for z in zones]
    data = listing_service.get_feed_data(user_id, zone_ids, [], "newest")
    return data["listings"]
