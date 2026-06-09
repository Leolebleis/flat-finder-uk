import logging
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger(__name__)

LOGIN_PATH = "/login"
PUBLIC_PATHS = {LOGIN_PATH, "/static"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        # Strip root_path prefix for comparison
        if request.app.root_path:
            path = path.removeprefix(request.app.root_path)
        if any(path.startswith(p) for p in PUBLIC_PATHS):
            return await call_next(request)
        user_id = request.session.get("user_id")
        if not user_id:
            return RedirectResponse(
                url=f"{request.app.root_path}{LOGIN_PATH}", status_code=303
            )
        return await call_next(request)
