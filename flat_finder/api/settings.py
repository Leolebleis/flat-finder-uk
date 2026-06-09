import logging
import threading
import time
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from flat_finder.geo import extract_coords_from_url
from flat_finder.scraper.commute import tfl_journey_mins
from sqlalchemy.orm import Session

from flat_finder.api.dependencies import (
    get_current_user_id,
    get_poi_service,
    get_user_service,
    get_zone_service,
)
from flat_finder.api.templating import templates
from flat_finder.pois.persistence import POICommuteRepository
from flat_finder.pois.service import POIService
from flat_finder.users.service import UserService
from flat_finder.zones.service import POI_COLORS, ZoneService

log = logging.getLogger(__name__)
router = APIRouter()

_TFL_BACKFILL_SLEEP_S = 0.5


def _backfill_poi(
    poi_id: int,
    poi_lat: float,
    poi_lng: float,
    session_factory: Callable[[], Session],
) -> None:
    """Background thread: fetch TfL commute times for all listings missing this POI."""
    session = session_factory()
    try:
        commute_repo = POICommuteRepository(session)
        rows = commute_repo.get_listings_missing_poi(poi_id)
        for row in rows:
            mins = tfl_journey_mins(row["latitude"], row["longitude"], poi_lat, poi_lng)
            if mins is None:
                continue
            commute_repo.upsert(row["id"], poi_id, mins)
            session.commit()
            time.sleep(_TFL_BACKFILL_SLEEP_S)
    finally:
        session.close()


@router.get("/settings", response_class=HTMLResponse, name="settings_page")
def settings_page(
    request: Request,
    user_id: Annotated[int, Depends(get_current_user_id)],
    poi_service: Annotated[POIService, Depends(get_poi_service)],
    zone_service: Annotated[ZoneService, Depends(get_zone_service)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> HTMLResponse:
    pois = poi_service.get_user_pois(user_id)
    zones = zone_service.get_user_zones(user_id)
    user = user_service.get_by_id(user_id)
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "pois": pois,
            "zones": zones,
            "poi_colors": POI_COLORS,
            "ntfy_topic": user.ntfy_topic if user else None,
        },
    )


@router.post("/settings/poi", name="add_poi")
def add_poi(
    request: Request,
    user_id: Annotated[int, Depends(get_current_user_id)],
    poi_service: Annotated[POIService, Depends(get_poi_service)],
    name: Annotated[str, Form()],
    maps_url: Annotated[str, Form()],
) -> RedirectResponse:
    coords = extract_coords_from_url(maps_url)
    if not coords or not name.strip():
        return RedirectResponse(request.url_for("settings_page"), status_code=303)
    lat, lng = coords
    poi = poi_service.add_poi(user_id, name.strip(), lat, lng)
    session_factory = request.app.state.session_factory
    threading.Thread(
        target=_backfill_poi,
        args=(poi["id"], lat, lng, session_factory),
        daemon=True,
    ).start()
    return RedirectResponse(request.url_for("settings_page"), status_code=303)


@router.delete("/settings/poi/{poi_id}", name="delete_poi")
def delete_poi_route(
    poi_id: int,
    user_id: Annotated[int, Depends(get_current_user_id)],
    poi_service: Annotated[POIService, Depends(get_poi_service)],
) -> dict[str, bool]:
    if not poi_service.delete_poi(user_id, poi_id):
        raise HTTPException(status_code=404, detail="POI not found")
    return {"ok": True}


@router.post("/settings/ntfy", name="update_ntfy")
def update_ntfy(
    request: Request,
    user_id: Annotated[int, Depends(get_current_user_id)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    topic: Annotated[str, Form()] = "",
) -> RedirectResponse:
    user_service.update_ntfy_topic(user_id, topic)
    return RedirectResponse(request.url_for("settings_page"), status_code=303)
