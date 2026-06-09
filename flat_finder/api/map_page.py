import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from flat_finder.api.dependencies import get_current_user_id
from flat_finder.api.templating import templates

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/map", response_class=HTMLResponse, name="map_page")
def map_page(
    request: Request,
    user_id: Annotated[int, Depends(get_current_user_id)],  # noqa: ARG001
) -> HTMLResponse:
    return templates.TemplateResponse(request, "map.html", {})
