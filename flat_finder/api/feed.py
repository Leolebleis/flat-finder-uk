import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from flat_finder.api.dependencies import (
    get_current_user_id,
    get_listing_service,
    get_poi_service,
    get_zone_service,
)
from flat_finder.api.templating import templates
from flat_finder.listings.service import ListingService
from flat_finder.pois.service import POIService
from flat_finder.zones.service import ZoneService

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_class=HTMLResponse, name="feed_page")
def feed_page(  # noqa: PLR0913
    request: Request,
    user_id: Annotated[int, Depends(get_current_user_id)],
    listing_service: Annotated[ListingService, Depends(get_listing_service)],
    zone_service: Annotated[ZoneService, Depends(get_zone_service)],
    poi_service: Annotated[POIService, Depends(get_poi_service)],
    sort: str = "newest",
    zone: str = "all",
) -> HTMLResponse:
    zones = zone_service.get_user_zones(user_id)
    pois = poi_service.get_user_pois(user_id)
    zone_ids = [z["id"] for z in zones]
    data = listing_service.get_feed_data(user_id, zone_ids, pois, sort, zone)
    data["zones_list"] = zones  # for zone filter dropdown
    data["zone"] = zone
    return templates.TemplateResponse(request, "feed.html", data)
