# Import all ORM models so their table mappings are registered on Base.metadata
# before create_all is called.
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlparse

import flat_finder.persistence  # noqa: F401
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from flat_finder.api.app import create_app
from flat_finder.database import Base
from flat_finder.users.persistence import UserRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def db_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine) -> Session:
    factory = sessionmaker(bind=db_engine)
    session = factory()
    yield session
    session.close()


@pytest.fixture
def app(db_engine):
    """Create a test FastAPI app backed by a temporary test DB.

    Bypasses the production lifespan (which tries to open config.DB_PATH) by
    injecting engine + session_factory directly onto app.state before the
    TestClient context manager starts the lifespan.  The test lifespan simply
    uses whatever is already on app.state.
    """

    @asynccontextmanager
    async def test_lifespan(_app: FastAPI) -> AsyncIterator[None]:  # noqa: PT019
        # engine + session_factory already injected below
        yield

    application = create_app()
    # Swap in test lifespan before the TestClient enters it
    application.router.lifespan_context = test_lifespan
    application.state.engine = db_engine
    application.state.session_factory = sessionmaker(bind=db_engine)
    return application


@pytest.fixture
def client(app) -> TestClient:
    """Unauthenticated test client."""
    with TestClient(app, root_path="/flat", raise_server_exceptions=True) as c:
        yield c


@pytest.fixture
def authed_client(app, db_session) -> TestClient:
    """Test client logged in as 'leo'."""
    repo = UserRepository(db_session)
    repo.create("leo")
    db_session.commit()

    with TestClient(app, root_path="/flat", raise_server_exceptions=True) as c:
        c.post("/login", data={"username": "leo"})
        yield c


def params_of(url: str) -> dict[str, list[str]]:
    """Decode a search URL's query string, for adapter URL-building tests."""
    return parse_qs(urlparse(url).query)
