import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from flat_finder.api.dependencies import (
    get_current_user_id,
    get_listing_service,
    get_poi_service,
)
from flat_finder.api.templating import templates
from flat_finder.listings.service import ListingService
from flat_finder.pois.service import POIService

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/listing/{listing_id}", response_class=HTMLResponse, name="detail_page")
def detail_page(
    listing_id: str,
    request: Request,
    user_id: Annotated[int, Depends(get_current_user_id)],
    listing_service: Annotated[ListingService, Depends(get_listing_service)],
    poi_service: Annotated[POIService, Depends(get_poi_service)],
) -> HTMLResponse:
    pois = poi_service.get_user_pois(user_id)
    data = listing_service.get_detail_data(user_id, listing_id, pois)
    if data is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return templates.TemplateResponse(request, "detail.html", data)
