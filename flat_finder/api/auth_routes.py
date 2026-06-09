import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from flat_finder.api.dependencies import get_user_service
from flat_finder.api.templating import templates
from flat_finder.users.service import UserService

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login", response_model=None)
def login_submit(
    request: Request,
    user_service: Annotated[UserService, Depends(get_user_service)],
    username: Annotated[str, Form()] = "",
) -> HTMLResponse | RedirectResponse:
    if not username.strip():
        return templates.TemplateResponse(
            request, "login.html", {"error": "Username is required"}, status_code=200
        )
    user = user_service.login(username)
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    log.info("Session created for user: %s (id=%d)", user.username, user.id)
    return RedirectResponse(url=request.app.root_path + "/", status_code=303)


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    username = request.session.get("username", "unknown")
    request.session.clear()
    log.info("User logged out: %s", username)
    return RedirectResponse(url=f"{request.app.root_path}/login", status_code=303)
