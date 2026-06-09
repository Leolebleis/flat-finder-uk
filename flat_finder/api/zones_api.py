import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from flat_finder.zone_utils import compute_zone_params, resolve_postcode, resolve_rightmove_id

from flat_finder.api.dependencies import get_current_user_id, get_zone_service
from flat_finder.api.schemas import ZoneCreateRequest
from flat_finder.zones.service import ZoneService

log = logging.getLogger(__name__)
router = APIRouter()


def _resolve_zone_payload(body: ZoneCreateRequest) -> tuple[dict, str | None, str | None]:
    """Validate and enrich a zone payload. Returns (params, postcode, rightmove_id)."""
    name = body.name.strip()
    if not body.geometry or not name:
        raise HTTPException(400, "name and geometry required")
    params = compute_zone_params(body.geometry)
    postcode = resolve_postcode(params["centroid_lat"], params["centroid_lng"])
    rightmove_id = resolve_rightmove_id(postcode) if postcode else None
    return params, postcode, rightmove_id


@router.get("/api/zones")
def api_zones(
    user_id: Annotated[int, Depends(get_current_user_id)],
    zone_service: Annotated[ZoneService, Depends(get_zone_service)],
) -> list[dict]:
    return zone_service.get_user_zones(user_id)


@router.post("/api/zones")
def api_create_zone(
    body: ZoneCreateRequest,
    user_id: Annotated[int, Depends(get_current_user_id)],
    zone_service: Annotated[ZoneService, Depends(get_zone_service)],
) -> dict:
    params, postcode, rightmove_id = _resolve_zone_payload(body)
    return zone_service.create_zone(
        user_id,
        name=body.name.strip(),
        geometry=json.dumps(body.geometry),
        centroid_lat=params["centroid_lat"],
        centroid_lng=params["centroid_lng"],
        covering_radius_km=params["covering_radius_km"],
        rightmove_id=rightmove_id,
        openrent_term=postcode,
    )


@router.put("/api/zones/{zone_id}")
def api_update_zone(
    zone_id: int,
    body: ZoneCreateRequest,
    user_id: Annotated[int, Depends(get_current_user_id)],
    zone_service: Annotated[ZoneService, Depends(get_zone_service)],
) -> dict:
    params, postcode, rightmove_id = _resolve_zone_payload(body)
    updated = zone_service.update_zone(
        user_id,
        zone_id,
        name=body.name.strip(),
        geometry=json.dumps(body.geometry),
        centroid_lat=params["centroid_lat"],
        centroid_lng=params["centroid_lng"],
        covering_radius_km=params["covering_radius_km"],
        rightmove_id=rightmove_id,
        openrent_term=postcode,
    )
    if not updated:
        raise HTTPException(404, "Zone not found")
    # Return fresh dict for the updated zone
    zones = zone_service.get_user_zones(user_id)
    zone = next((z for z in zones if z["id"] == zone_id), None)
    if not zone:
        raise HTTPException(404, "Zone not found")
    return zone


@router.delete("/api/zones/{zone_id}")
def api_delete_zone(
    zone_id: int,
    user_id: Annotated[int, Depends(get_current_user_id)],
    zone_service: Annotated[ZoneService, Depends(get_zone_service)],
) -> dict[str, bool]:
    if not zone_service.delete_zone(user_id, zone_id):
        raise HTTPException(404, "Zone not found")
    return {"ok": True}
