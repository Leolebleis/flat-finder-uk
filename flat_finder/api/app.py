import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from flat_finder import config
from flat_finder.api.auth_routes import router as auth_router
from flat_finder.api.detail import router as detail_router
from flat_finder.api.feed import router as feed_router
from flat_finder.api.listings_api import router as listings_api_router
from flat_finder.api.map_page import router as map_router
from flat_finder.api.settings import router as settings_router
from flat_finder.api.state_api import router as state_api_router
from flat_finder.api.zones_api import router as zones_api_router
from flat_finder.database import Base, get_engine, get_session
from flat_finder.users.auth import AuthMiddleware

log = logging.getLogger(__name__)

_pkg_dir = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = get_engine(config.DB_PATH)
    Base.metadata.create_all(engine)  # For now; will be replaced by alembic upgrade
    app.state.engine = engine
    app.state.session_factory = get_session(engine)
    log.info("Application started, DB at %s", config.DB_PATH)
    yield
    engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Flat Finder", root_path="/flat", lifespan=lifespan)

    # Middleware order: AuthMiddleware is added first, SessionMiddleware second.
    # Starlette wraps in reverse order, so SessionMiddleware runs first (populating
    # request.session), then AuthMiddleware checks the session.
    app.add_middleware(AuthMiddleware)
    app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY)

    # Mount static files
    static_dir = _pkg_dir / "static"
    if not static_dir.exists():
        static_dir.mkdir(parents=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(auth_router)
    app.include_router(feed_router)
    app.include_router(detail_router)
    app.include_router(map_router)
    app.include_router(settings_router)
    app.include_router(zones_api_router)
    app.include_router(state_api_router)
    app.include_router(listings_api_router)

    return app


app = create_app()
