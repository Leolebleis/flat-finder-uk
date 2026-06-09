import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from flat_finder.api.dependencies import get_current_user_id, get_listing_service
from flat_finder.api.schemas import StateUpdateRequest
from flat_finder.listings.service import ListingService

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/state/{listing_id}")
def update_state(
    listing_id: str,
    body: StateUpdateRequest,
    user_id: Annotated[int, Depends(get_current_user_id)],
    listing_service: Annotated[ListingService, Depends(get_listing_service)],
) -> dict[str, Any]:
    # Verify listing exists before upserting state
    detail = listing_service.get_detail_data(user_id, listing_id, [])
    if detail is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    updates = body.model_dump(include=body.model_fields_set)
    return listing_service.update_state(user_id, listing_id, updates)
