# Multi-User + Architecture Restructure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure flat-finder toward Clean Architecture (SQLAlchemy + Alembic, domain-first folders) and add multi-user support (username login, per-user zones/POIs/state, per-user ntfy, listing archive).

**Architecture:** Domain-first package layout under `flat_finder/`. Each domain module (listings, zones, pois, users) has domain entities (frozen dataclasses), DAO protocols, SQLAlchemy persistence, and service classes. FastAPI routes in `flat_finder/api/`. Scraper in `flat_finder/scraper/`. Alembic manages all migrations. TDD throughout — E2E tests hit the full stack (TestClient + real SQLite DB), no mocks except third-party HTTP APIs.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0 (sync), Alembic (batch mode), Jinja2, Pydantic, import-linter, pytest, httpx, uv.

**Spec:** `docs/superpowers/specs/2026-06-08-multi-user-design.md`

**Testing approach:** TDD. E2E tests are UX-driven (Given/When/Then docstrings), cover happy + unhappy paths, use real DB (no mocks except third-party APIs: TfL, ntfy, Gmail, Rightmove, OpenRent, postcodes.io). Unit tests for service business logic. Class-based test grouping by feature.

**Logging:** Use `logging.getLogger(__name__)` in modules. Log key operations (login, scrape start/end, notifications sent, state changes, migration steps). No comments unless the WHY is non-obvious.

**Deliverable:** Feature branch `feat/multi-user`, PR to main, Docker build for manual testing.

---

## File Structure

### New package: `flat_finder/`

```
flat_finder/
  __init__.py
  config.py                 # env vars (port from shared/config.py)
  database.py               # SQLAlchemy engine, session factory, Base
  geo.py                    # coord extraction (port from shared/geo.py)
  scraping.py               # exclude filters (port from shared/scraping.py)
  zone_utils.py             # polygon math (port from shared/zones.py)

  listings/
    __init__.py
    model.py                # Listing, ListingState domain entities
    dao.py                  # ListingDAO, ListingStateDAO protocols
    service.py              # ListingService (feed, detail, scoring)
    persistence.py          # ListingDB, ListingStateDB, ListingArchiveDB ORM + DAO impls

  zones/
    __init__.py
    model.py                # Zone domain entity
    dao.py                  # ZoneDAO, ListingZoneDAO protocols
    service.py              # ZoneService
    persistence.py          # ZoneDB, ListingZoneDB ORM + DAO impls

  pois/
    __init__.py
    model.py                # POI, POICommute domain entities
    dao.py                  # POIDAO, POICommuteDAO protocols
    service.py              # POIService (incl. backfill)
    persistence.py          # POIDB, POICommuteDB ORM + DAO impls

  users/
    __init__.py
    model.py                # User domain entity
    dao.py                  # UserDAO protocol
    service.py              # UserService
    persistence.py          # UserDB ORM + DAO impl
    auth.py                 # get_current_user dependency, session helpers

  scraper/
    __init__.py
    runner.py               # main scrape loop (port from scraper/scraper.py)
    rightmove.py            # port from scraper/rightmove.py
    openrent.py             # port from scraper/openrent.py
    commute.py              # port from scraper/commute.py
    notifier.py             # port from scraper/notifier.py

  api/
    __init__.py
    app.py                  # FastAPI app, SessionMiddleware, lifespan, route mounting
    dependencies.py         # Depends() factories: get_db, get_current_user, get_*_service
    schemas.py              # Pydantic request/response models (StateUpdate, ZoneIn, etc.)
    feed.py                 # GET / (feed page)
    detail.py               # GET /listing/{id}
    map_page.py             # GET /map
    settings.py             # GET /settings, POST /settings/poi, POST /settings/ntfy
    auth_routes.py          # GET/POST /login, POST /logout
    zones_api.py            # GET/POST/PUT/DELETE /api/zones
    state_api.py            # POST /api/state/{listing_id}
    listings_api.py         # GET /api/listings

  templates/                # port from ui/templates/
    base.html               # updated: add username + logout in nav
    login.html              # NEW
    _macros.html
    feed.html
    detail.html
    map.html
    settings.html           # updated: add ntfy topic field

  static/                   # port from ui/static/ (unchanged)
    v2.css
    v2.js
    map.js

alembic/                    # repo root
  alembic.ini
  env.py
  versions/
    001_multi_user.py       # initial migration

tests/
  conftest.py               # shared fixtures: db_engine, db_session, client, seeded users
  test_auth.py              # E2E: login, logout, session, redirects
  test_feed.py              # E2E: feed page, zone filtering, user scoping
  test_detail.py            # E2E: detail page, user state
  test_settings.py          # E2E: POI/zone/ntfy management
  test_zones_api.py         # E2E: zone CRUD, user isolation
  test_state_api.py         # E2E: listing state, user isolation
  test_scraper.py           # Unit: scraper with mocked HTTP
  test_notifier.py          # Unit: notification formatting
  test_services.py          # Unit: service logic (scoring, dedup)
  test_migration.py         # Migration on existing DB
  test_geo.py               # Unit: coord extraction
  test_commute.py           # Unit: TfL API
```

### Modified files

- `pyproject.toml` — packages -> `["flat_finder"]`, add sqlalchemy/alembic/itsdangerous deps, update ruff/coverage/hatch config
- `docker-compose.yml` — add SECRET_KEY, remove NTFY_TOPIC
- `ui/Dockerfile` -> `Dockerfile.ui` — COPY flat_finder/, update CMD
- `scraper/Dockerfile` -> `Dockerfile.scraper` — COPY flat_finder/, update CMD
- `.github/workflows/ci.yml` — update paths, add import-linter step

### Deleted (after port complete)

- `shared/` (entire directory)
- `scraper/` (entire directory, replaced by `flat_finder/scraper/`)
- `ui/` (entire directory, replaced by `flat_finder/api/` + `flat_finder/templates/` + `flat_finder/static/`)

---

## Task 1: Create feature branch + add dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Create feature branch**

```bash
git checkout -b feat/multi-user
```

- [ ] **Step 2: Add runtime dependencies**

Add to `pyproject.toml` `[project] dependencies`:
```toml
"sqlalchemy>=2.0",
"alembic>=1.15",
"itsdangerous>=2.2",
```

- [ ] **Step 3: Add dev dependency**

Add to `[dependency-groups] dev`:
```toml
"import-linter>=2.11",
```

- [ ] **Step 4: Install**

```bash
uv sync
```
Verify: `uv run python -c "import sqlalchemy; import alembic; import itsdangerous; print('OK')"`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add sqlalchemy, alembic, itsdangerous, import-linter deps"
```

---

## Task 2: Create package skeleton + database engine

**Files:**
- Create: `flat_finder/__init__.py` and all subdirectory `__init__.py` files
- Create: `flat_finder/config.py`
- Create: `flat_finder/database.py`
- Test: `tests/test_database.py`

- [ ] **Step 1: Create directory structure**

Create all `__init__.py` files:
```
flat_finder/__init__.py
flat_finder/listings/__init__.py
flat_finder/zones/__init__.py
flat_finder/pois/__init__.py
flat_finder/users/__init__.py
flat_finder/scraper/__init__.py
flat_finder/api/__init__.py
```

- [ ] **Step 2: Write config.py**

Port from `shared/config.py`. Add `SECRET_KEY`:
```python
import os
from pathlib import Path

def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)

DB_PATH = Path(get_env("FLAT_FINDER_DB", "/app/data/flat_finder.db"))
SECRET_KEY = get_env("SECRET_KEY", "dev-secret-change-in-production")
GMAIL_ADDRESS = get_env("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = get_env("GMAIL_APP_PASSWORD", "")
MAX_RENT_PCM = int(get_env("MAX_RENT_PCM", "2200"))
MIN_BEDROOMS = int(get_env("MIN_BEDROOMS", "1"))
MAX_BEDROOMS = int(get_env("MAX_BEDROOMS", "2"))
```

- [ ] **Step 3: Write failing test for database engine**

```python
# tests/test_database.py
from sqlalchemy import text

from flat_finder.database import Base, get_engine, get_session


class TestDatabaseEngine:
    """Feature: Database connectivity

    As the application, I can connect to SQLite
    so that all components share a single DB.
    """

    def test_engine_connects_to_sqlite(self, tmp_path):
        """Given a path to a SQLite file
        When I create an engine
        Then I can execute queries
        """
        db_path = tmp_path / "test.db"
        engine = get_engine(db_path)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

    def test_session_factory_returns_working_session(self, tmp_path):
        """Given a database engine
        When I create a session
        Then I can use it to query the database
        """
        db_path = tmp_path / "test.db"
        engine = get_engine(db_path)
        Base.metadata.create_all(engine)
        session = get_session(engine)
        with session() as s:
            result = s.execute(text("SELECT 1"))
            assert result.scalar() == 1

    def test_engine_uses_wal_mode(self, tmp_path):
        """Given a new engine
        When I check the journal mode
        Then it is WAL (for concurrent access)
        """
        db_path = tmp_path / "test.db"
        engine = get_engine(db_path)
        with engine.connect() as conn:
            mode = conn.execute(text("PRAGMA journal_mode")).scalar()
            assert mode == "wal"
```

- [ ] **Step 4: Run test, verify it fails**

```bash
uv run pytest tests/test_database.py -v
```
Expected: FAIL (ImportError — `flat_finder.database` doesn't exist yet)

- [ ] **Step 5: Write database.py**

```python
# flat_finder/database.py
import logging
from pathlib import Path

from sqlalchemy import event, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def _set_sqlite_pragmas(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def get_engine(db_path: Path) -> Engine:
    url = f"sqlite:///{db_path}"
    engine = create_engine(url)
    event.listen(engine, "connect", _set_sqlite_pragmas)
    log.info("Database engine created: %s", db_path)
    return engine


def get_session(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine)
```

- [ ] **Step 6: Run test, verify it passes**

```bash
uv run pytest tests/test_database.py -v
```
Expected: 3 PASSED

- [ ] **Step 7: Commit**

```bash
git add flat_finder/ tests/test_database.py
git commit -m "feat: add flat_finder package skeleton + SQLAlchemy engine"
```

---

## Task 3: SQLAlchemy ORM models

**Files:**
- Create: `flat_finder/listings/persistence.py`
- Create: `flat_finder/zones/persistence.py`
- Create: `flat_finder/pois/persistence.py`
- Create: `flat_finder/users/persistence.py`
- Test: `tests/test_orm_models.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_orm_models.py
from flat_finder.database import Base, get_engine
from flat_finder.listings.persistence import ListingDB, ListingStateDB, ListingArchiveDB
from flat_finder.zones.persistence import ZoneDB, ListingZoneDB
from flat_finder.pois.persistence import POIDB, POICommuteDB
from flat_finder.users.persistence import UserDB


class TestORMModels:
    """Feature: Database schema

    As the application, the ORM models create
    the correct tables with the correct columns.
    """

    def test_all_tables_created(self, tmp_path):
        """Given all ORM models are imported
        When I create_all on a fresh database
        Then all 9 tables exist
        """
        engine = get_engine(tmp_path / "test.db")
        Base.metadata.create_all(engine)
        table_names = set(Base.metadata.tables.keys())
        assert table_names == {
            "listings", "listing_zones", "listings_archive",
            "scraper_state", "zones", "pois", "poi_commutes",
            "users", "user_state",
        }

    def test_user_state_has_composite_pk(self, tmp_path):
        """Given the user_state table
        When I inspect its primary key
        Then it is (user_id, listing_id)
        """
        engine = get_engine(tmp_path / "test.db")
        Base.metadata.create_all(engine)
        pk_cols = [c.name for c in ListingStateDB.__table__.primary_key.columns]
        assert pk_cols == ["user_id", "listing_id"]

    def test_zones_has_user_id(self, tmp_path):
        """Given the zones table
        When I inspect its columns
        Then user_id is present and non-nullable
        """
        col = ZoneDB.__table__.c.user_id
        assert not col.nullable

    def test_pois_has_user_id(self, tmp_path):
        """Given the pois table
        When I inspect its columns
        Then user_id is present and non-nullable
        """
        col = POIDB.__table__.c.user_id
        assert not col.nullable
```

- [ ] **Step 2: Run test, verify it fails**

```bash
uv run pytest tests/test_orm_models.py -v
```

- [ ] **Step 3: Write users/persistence.py**

```python
# flat_finder/users/persistence.py
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from flat_finder.database import Base


class UserDB(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    ntfy_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
```

- [ ] **Step 4: Write listings/persistence.py**

```python
# flat_finder/listings/persistence.py
from sqlalchemy import Boolean, DateTime, Integer, Real, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from flat_finder.database import Base


class ListingDB(Base):
    __tablename__ = "listings"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    price_pcm: Mapped[int | None] = mapped_column(Integer)
    bedrooms: Mapped[int | None] = mapped_column(Integer)
    address: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Real)
    longitude: Mapped[float | None] = mapped_column(Real)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    property_type: Mapped[str | None] = mapped_column(Text)
    furnishing: Mapped[str | None] = mapped_column(Text)
    sqft: Mapped[int | None] = mapped_column(Integer)
    has_dishwasher: Mapped[str] = mapped_column(Text, default="unknown")
    has_washer: Mapped[str] = mapped_column(Text, default="unknown")
    has_outdoor: Mapped[str] = mapped_column(Text, default="unknown")
    outdoor_type: Mapped[str | None] = mapped_column(Text)
    zone: Mapped[str | None] = mapped_column(Text)
    first_seen: Mapped[str] = mapped_column(DateTime, nullable=False)
    listing_date: Mapped[str | None] = mapped_column(Text)


class ListingStateDB(Base):
    __tablename__ = "user_state"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[str] = mapped_column(Text, primary_key=True)
    seen: Mapped[bool] = mapped_column(Boolean, default=False)
    favourite: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    override_dishwasher: Mapped[str | None] = mapped_column(Text)
    override_washer: Mapped[str | None] = mapped_column(Text)
    override_outdoor: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[str | None] = mapped_column(DateTime)


class ListingArchiveDB(Base):
    __tablename__ = "listings_archive"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    price_pcm: Mapped[int | None] = mapped_column(Integer)
    bedrooms: Mapped[int | None] = mapped_column(Integer)
    address: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Real)
    longitude: Mapped[float | None] = mapped_column(Real)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    property_type: Mapped[str | None] = mapped_column(Text)
    furnishing: Mapped[str | None] = mapped_column(Text)
    sqft: Mapped[int | None] = mapped_column(Integer)
    has_dishwasher: Mapped[str] = mapped_column(Text, default="unknown")
    has_washer: Mapped[str] = mapped_column(Text, default="unknown")
    has_outdoor: Mapped[str] = mapped_column(Text, default="unknown")
    outdoor_type: Mapped[str | None] = mapped_column(Text)
    zone: Mapped[str | None] = mapped_column(Text)
    first_seen: Mapped[str] = mapped_column(DateTime, nullable=False)
    listing_date: Mapped[str | None] = mapped_column(Text)


class ScraperStateDB(Base):
    __tablename__ = "scraper_state"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
```

- [ ] **Step 5: Write zones/persistence.py**

```python
# flat_finder/zones/persistence.py
from sqlalchemy import Integer, Real, Text
from sqlalchemy.orm import Mapped, mapped_column

from flat_finder.database import Base


class ZoneDB(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    geometry: Mapped[str] = mapped_column(Text, nullable=False)
    centroid_lat: Mapped[float] = mapped_column(Real, nullable=False)
    centroid_lng: Mapped[float] = mapped_column(Real, nullable=False)
    covering_radius_km: Mapped[float] = mapped_column(Real, nullable=False)
    rightmove_id: Mapped[str | None] = mapped_column(Text)
    openrent_term: Mapped[str | None] = mapped_column(Text)
    color_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class ListingZoneDB(Base):
    __tablename__ = "listing_zones"

    listing_id: Mapped[str] = mapped_column(Text, primary_key=True)
    zone_id: Mapped[int] = mapped_column(Integer, primary_key=True)
```

- [ ] **Step 6: Write pois/persistence.py**

```python
# flat_finder/pois/persistence.py
from sqlalchemy import Integer, Real, Text
from sqlalchemy.orm import Mapped, mapped_column

from flat_finder.database import Base


class POIDB(Base):
    __tablename__ = "pois"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    lat: Mapped[float] = mapped_column(Real, nullable=False)
    lng: Mapped[float] = mapped_column(Real, nullable=False)
    color_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class POICommuteDB(Base):
    __tablename__ = "poi_commutes"

    listing_id: Mapped[str] = mapped_column(Text, primary_key=True)
    poi_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commute_mins: Mapped[int] = mapped_column(Integer, nullable=False)
```

- [ ] **Step 7: Run tests, verify they pass**

```bash
uv run pytest tests/test_orm_models.py -v
```

- [ ] **Step 8: Commit**

```bash
git add flat_finder/*/persistence.py tests/test_orm_models.py
git commit -m "feat: add SQLAlchemy ORM models for all tables"
```

---

## Task 4: Domain entities + DAO protocols

**Files:**
- Create: `flat_finder/users/model.py`, `flat_finder/users/dao.py`
- Create: `flat_finder/listings/model.py`, `flat_finder/listings/dao.py`
- Create: `flat_finder/zones/model.py`, `flat_finder/zones/dao.py`
- Create: `flat_finder/pois/model.py`, `flat_finder/pois/dao.py`

Domain entities are frozen dataclasses. DAO protocols define the persistence interface. No tests needed for these — they're type definitions. Tested via DAO implementations in Task 5.

- [ ] **Step 1: Write users domain**

`flat_finder/users/model.py`:
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class User:
    id: int
    username: str
    ntfy_topic: str | None
    created_at: str
```

`flat_finder/users/dao.py`:
```python
from typing import Protocol
from flat_finder.users.model import User

class UserDAO(Protocol):
    def get_by_id(self, user_id: int) -> User | None: ...
    def get_by_username(self, username: str) -> User | None: ...
    def create(self, username: str) -> User: ...
    def update_ntfy_topic(self, user_id: int, topic: str | None) -> None: ...
    def get_all_with_ntfy(self) -> list[User]: ...
```

- [ ] **Step 2: Write listings domain**

`flat_finder/listings/model.py`:
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Listing:
    id: str
    source: str
    url: str
    title: str | None
    price_pcm: int | None
    bedrooms: int | None
    address: str | None
    latitude: float | None
    longitude: float | None
    description: str | None
    image_url: str | None
    property_type: str | None
    furnishing: str | None
    sqft: int | None
    has_dishwasher: str
    has_washer: str
    has_outdoor: str
    outdoor_type: str | None
    zone: str | None
    first_seen: str
    listing_date: str | None

@dataclass(frozen=True)
class ListingState:
    user_id: int
    listing_id: str
    seen: bool
    favourite: bool
    notes: str | None
    override_dishwasher: str | None
    override_washer: str | None
    override_outdoor: str | None
    updated_at: str | None
```

`flat_finder/listings/dao.py`:
```python
from typing import Any, Protocol
from flat_finder.listings.model import Listing, ListingState

class ListingDAO(Protocol):
    def insert(self, listing: dict[str, Any]) -> bool: ...
    def get_all_with_state(self, user_id: int, zone_ids: list[int]) -> list[dict[str, Any]]: ...
    def get_by_id(self, listing_id: str) -> Listing | None: ...
    def get_listings_in_zone_polygon(self, geometry_geojson: str) -> list[Listing]: ...
    def archive_old(self, days: int) -> int: ...

class ListingStateDAO(Protocol):
    def get(self, user_id: int, listing_id: str) -> ListingState | None: ...
    def upsert(self, user_id: int, listing_id: str, updates: dict[str, Any]) -> ListingState: ...
    def delete_for_listings(self, listing_ids: list[str]) -> None: ...
```

- [ ] **Step 3: Write zones domain**

`flat_finder/zones/model.py`:
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Zone:
    id: int
    user_id: int
    name: str
    geometry: str
    centroid_lat: float
    centroid_lng: float
    covering_radius_km: float
    rightmove_id: str | None
    openrent_term: str | None
    color_index: int
    created_at: str
```

`flat_finder/zones/dao.py`:
```python
from typing import Protocol
from flat_finder.zones.model import Zone

class ZoneDAO(Protocol):
    def get_by_user(self, user_id: int) -> list[Zone]: ...
    def get_all(self) -> list[Zone]: ...
    def get_by_id(self, zone_id: int) -> Zone | None: ...
    def create(self, user_id: int, name: str, geometry: str, centroid_lat: float,
               centroid_lng: float, covering_radius_km: float, rightmove_id: str | None,
               openrent_term: str | None, color_index: int) -> Zone: ...
    def update(self, zone_id: int, **kwargs: object) -> None: ...
    def delete(self, zone_id: int) -> None: ...

class ListingZoneDAO(Protocol):
    def link(self, listing_id: str, zone_id: int) -> None: ...
    def get_zone_ids_for_listing(self, listing_id: str) -> list[int]: ...
    def get_listing_ids_for_zones(self, zone_ids: list[int]) -> list[str]: ...
    def delete_for_listings(self, listing_ids: list[str]) -> None: ...
```

- [ ] **Step 4: Write pois domain**

`flat_finder/pois/model.py`:
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class POI:
    id: int
    user_id: int
    name: str
    lat: float
    lng: float
    color_index: int
    created_at: str

@dataclass(frozen=True)
class POICommute:
    listing_id: str
    poi_id: int
    commute_mins: int
```

`flat_finder/pois/dao.py`:
```python
from typing import Protocol
from flat_finder.pois.model import POI

class POIDAO(Protocol):
    def get_by_user(self, user_id: int) -> list[POI]: ...
    def get_all(self) -> list[POI]: ...
    def create(self, user_id: int, name: str, lat: float, lng: float, color_index: int) -> POI: ...
    def delete(self, poi_id: int) -> None: ...

class POICommuteDAO(Protocol):
    def upsert(self, listing_id: str, poi_id: int, commute_mins: int) -> None: ...
    def get_for_listings(self, listing_ids: list[str]) -> dict[str, dict[int, int]]: ...
    def get_listings_missing_poi(self, poi_id: int) -> list[dict]: ...
    def delete_for_listings(self, listing_ids: list[str]) -> None: ...
```

- [ ] **Step 5: Commit**

```bash
git add flat_finder/*/model.py flat_finder/*/dao.py
git commit -m "feat: add domain entities and DAO protocols for all domains"
```

---

## Task 5: DAO implementations + test fixtures

**Files:**
- Modify: `flat_finder/users/persistence.py` (add UserRepository)
- Modify: `flat_finder/listings/persistence.py` (add ListingRepository, ListingStateRepository)
- Modify: `flat_finder/zones/persistence.py` (add ZoneRepository, ListingZoneRepository)
- Modify: `flat_finder/pois/persistence.py` (add POIRepository, POICommuteRepository)
- Create: `tests/conftest.py`
- Test: `tests/test_repositories.py`

This task adds concrete DAO implementations that use SQLAlchemy sessions. Each repository class implements the corresponding DAO protocol and maps between ORM models and domain entities.

- [ ] **Step 1: Write conftest.py with shared fixtures**

```python
# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from flat_finder.database import Base


@pytest.fixture
def db_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()
```

- [ ] **Step 2: Write failing repository tests**

Write `tests/test_repositories.py` with E2E tests for each repository. Test user creation, zone CRUD with user scoping, POI with user scoping, listing state with user+listing composite key, listing_zones linking. Key tests:

```python
class TestUserRepository:
    """Feature: User management"""

    def test_create_user_and_retrieve_by_username(self, db_session):
        """Given no users exist
        When I create user "amelie"
        Then I can retrieve her by username
        """
        repo = UserRepository(db_session)
        user = repo.create("amelie")
        found = repo.get_by_username("amelie")
        assert found is not None
        assert found.username == "amelie"
        assert found.id == user.id

    def test_create_duplicate_username_fails(self, db_session):
        """Given user "leo" exists
        When I try to create another "leo"
        Then it raises an error
        """
        ...

class TestZoneRepository:
    """Feature: Per-user zone management"""

    def test_zones_scoped_to_user(self, db_session):
        """Given user A has zone "South London" and user B has zone "Brixton"
        When I query zones for user A
        Then I only see "South London"
        """
        ...

class TestListingStateRepository:
    """Feature: Per-user listing state"""

    def test_state_independent_per_user(self, db_session):
        """Given user A marks listing X as favourite
        When user B checks listing X
        Then it is not favourite for user B
        """
        ...
```

- [ ] **Step 3: Implement all repository classes**

Add repository classes to each `persistence.py` file. Each repository takes a `Session` in its constructor, maps between ORM models and domain entities, and implements the DAO protocol. Use `datetime.now(UTC).isoformat()` for timestamps.

Key pattern:
```python
class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, username: str) -> User:
        db_user = UserDB(username=username, created_at=datetime.now(UTC).isoformat())
        self._session.add(db_user)
        self._session.flush()
        return User(id=db_user.id, username=db_user.username, ...)

    def get_by_username(self, username: str) -> User | None:
        row = self._session.query(UserDB).filter_by(username=username).first()
        return User(...) if row else None
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
uv run pytest tests/test_repositories.py -v
```

- [ ] **Step 5: Commit**

```bash
git add flat_finder/*/persistence.py tests/conftest.py tests/test_repositories.py
git commit -m "feat: add DAO implementations with user-scoped queries"
```

---

## Task 6: Alembic setup + initial migration

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/001_multi_user.py`
- Test: `tests/test_migration.py`

- [ ] **Step 1: Initialize Alembic**

```bash
uv run alembic init alembic
```

- [ ] **Step 2: Configure alembic.ini**

Set `sqlalchemy.url` to empty (will be overridden in env.py). Set `file_template` to `%%(rev)s_%%(slug)s`.

- [ ] **Step 3: Configure alembic/env.py**

Import `Base` from `flat_finder.database` and all persistence modules (to register ORM models). Set `target_metadata = Base.metadata`. Configure `render_as_batch=True` for SQLite batch mode. Read DB path from `flat_finder.config.DB_PATH`.

- [ ] **Step 4: Write failing migration test**

```python
# tests/test_migration.py
import sqlite3

class TestMigrationFromExistingDB:
    """Feature: Data migration

    As an existing user, my data is preserved
    when the app upgrades to multi-user.
    """

    def test_existing_zones_assigned_to_leo(self, tmp_path):
        """Given an existing DB with zones but no users table
        When the migration runs
        Then all zones have user_id = 1 (leo)
        And a "leo" user exists
        """
        db_path = tmp_path / "legacy.db"
        # Create legacy schema (no users table, no user_id columns)
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE zones (id INTEGER PRIMARY KEY, name TEXT, ...)")
        conn.execute("INSERT INTO zones (name, ...) VALUES ('South London', ...)")
        conn.close()
        # Run migration
        ...
        # Verify
        conn = sqlite3.connect(db_path)
        assert conn.execute("SELECT username FROM users WHERE id = 1").fetchone()[0] == "leo"
        assert conn.execute("SELECT user_id FROM zones WHERE name = 'South London'").fetchone()[0] == 1
        conn.close()

    def test_listing_zones_backfilled_from_zone_column(self, tmp_path):
        """Given existing listings with zone names
        When the migration runs
        Then listing_zones rows link each listing to its zone
        """
        ...
```

- [ ] **Step 5: Write the migration**

Create `alembic/versions/001_multi_user.py`. The migration must handle both fresh DBs and existing DBs. Key operations (all in batch mode):
1. Create `users` table
2. Insert "leo" user if migrating from existing DB
3. Add `user_id` column to `zones`, `pois` (default 1 for backfill)
4. Recreate `user_state` with composite PK `(user_id, listing_id)`
5. Create `listing_zones` table
6. Backfill `listing_zones` from listings.zone column
7. Create `listings_archive` table with analytics indexes

- [ ] **Step 6: Run migration test**

```bash
uv run pytest tests/test_migration.py -v
```

- [ ] **Step 7: Commit**

```bash
git add alembic/ alembic.ini tests/test_migration.py
git commit -m "feat: add Alembic setup + initial multi-user migration"
```

---

## Task 7: Service layer

**Files:**
- Create: `flat_finder/users/service.py`
- Create: `flat_finder/listings/service.py`
- Create: `flat_finder/zones/service.py`
- Create: `flat_finder/pois/service.py`
- Test: `tests/test_services.py`

Services encapsulate business logic. They depend on DAO protocols (injected). Tests mock the DAOs.

- [ ] **Step 1: Write UserService**

```python
# flat_finder/users/service.py
import logging
from flat_finder.users.dao import UserDAO
from flat_finder.users.model import User

log = logging.getLogger(__name__)

class UserService:
    def __init__(self, user_dao: UserDAO) -> None:
        self._dao = user_dao

    def login(self, username: str) -> User:
        user = self._dao.get_by_username(username.strip().lower())
        if user:
            log.info("User logged in: %s", user.username)
            return user
        user = self._dao.create(username.strip().lower())
        log.info("New user created: %s", user.username)
        return user

    def update_ntfy_topic(self, user_id: int, topic: str | None) -> None:
        self._dao.update_ntfy_topic(user_id, topic.strip() if topic else None)
```

- [ ] **Step 2: Write ListingService**

Port scoring logic from `ui/main.py:_compute_scores`. Port `_normalize_listing`, `_apply_overrides`, sort logic. The service takes `ListingDAO`, `ListingStateDAO`, `POICommuteDAO` as dependencies.

Key methods:
- `get_feed_data(user_id, zone_ids, sort, zone_filter)` — returns listings with state, commutes, scores
- `get_detail_data(user_id, listing_id)` — returns single listing with state and commutes
- `update_state(user_id, listing_id, updates)` — upserts user state

- [ ] **Step 3: Write ZoneService**

Port zone resolution logic from `ui/main.py`. Key methods:
- `get_user_zones(user_id)` — list zones with colors
- `create_zone(user_id, name, geometry)` — resolve postcode/rightmove_id, insert, trigger backfill
- `update_zone(user_id, zone_id, name, geometry)` — verify ownership, update
- `delete_zone(user_id, zone_id)` — verify ownership, delete

- [ ] **Step 4: Write POIService**

Port from `ui/main.py`. Key methods:
- `get_user_pois(user_id)` — list POIs with colors
- `add_poi(user_id, name, maps_url)` — extract coords, insert, trigger commute backfill
- `delete_poi(user_id, poi_id)` — verify ownership, delete with commutes

- [ ] **Step 5: Write unit tests for services**

```python
# tests/test_services.py
class TestUserServiceLogin:
    """Feature: User login

    As a user, I can log in with my username
    and my account is created automatically if it doesn't exist.
    """

    def test_login_existing_user(self):
        """Given user "leo" exists
        When "leo" logs in
        Then the existing user is returned (not a new one)
        """
        ...

    def test_login_new_user_creates_account(self):
        """Given no users exist
        When "amelie" logs in
        Then a new user "amelie" is created and returned
        """
        ...

    def test_login_normalizes_username(self):
        """Given no users exist
        When " Leo " logs in (with spaces and caps)
        Then user "leo" is created (trimmed and lowered)
        """
        ...

class TestListingServiceScoring:
    """Feature: Weighted match scoring"""

    def test_score_computed_from_poi_commutes(self):
        """Given 2 listings with commute times to 2 POIs
        When I compute scores with equal weights
        Then the listing with shorter commutes scores higher
        """
        ...
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_services.py -v
```

- [ ] **Step 7: Commit**

```bash
git add flat_finder/*/service.py tests/test_services.py
git commit -m "feat: add service layer with scoring, user login, zone/poi management"
```

---

## Task 8: Auth middleware + login/logout routes

**Files:**
- Create: `flat_finder/users/auth.py`
- Create: `flat_finder/api/auth_routes.py`
- Create: `flat_finder/api/dependencies.py`
- Create: `flat_finder/api/app.py`
- Create: `flat_finder/templates/login.html`
- Modify: `flat_finder/templates/base.html` (port from `ui/templates/base.html`, add username + logout)
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write E2E auth tests**

```python
# tests/test_auth.py
class TestLogin:
    """Feature: User Authentication

    As a user, I can log in with just my username
    so that I have a personalized experience.
    """

    def test_unauthenticated_user_redirected_to_login(self, client):
        """Given I am not logged in
        When I visit the feed page
        Then I am redirected to /login
        """
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    def test_login_page_renders(self, client):
        """Given I am not logged in
        When I visit /login
        Then I see the login form
        """
        response = client.get("/login")
        assert response.status_code == 200
        assert "username" in response.text.lower()

    def test_login_with_new_username(self, client):
        """Given no users exist
        When I submit username "amelie"
        Then I am redirected to the feed
        And my session is set
        """
        response = client.post("/login", data={"username": "amelie"}, follow_redirects=False)
        assert response.status_code == 303
        # Follow redirect to verify session works
        feed = client.get("/", follow_redirects=True)
        assert feed.status_code == 200

    def test_login_with_existing_username(self, client, seed_user_leo):
        """Given user "leo" exists
        When I submit username "leo"
        Then I am logged in as the existing user (not a duplicate)
        """
        ...

    def test_login_empty_username_rejected(self, client):
        """Given I am on the login page
        When I submit an empty username
        Then I stay on the login page with an error
        """
        response = client.post("/login", data={"username": ""}, follow_redirects=False)
        assert response.status_code == 200  # re-renders login page

class TestLogout:
    """Feature: User Logout"""

    def test_logout_clears_session(self, authed_client):
        """Given I am logged in
        When I POST to /logout
        Then my session is cleared
        And I am redirected to /login
        """
        response = authed_client.post("/logout", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers["location"]
        # Verify session is gone
        feed = authed_client.get("/", follow_redirects=False)
        assert feed.status_code == 303  # redirected to login again

class TestNavBar:
    """Feature: Navigation shows user context"""

    def test_nav_shows_username(self, authed_client):
        """Given I am logged in as "leo"
        When I view any page
        Then the nav bar shows my username
        """
        response = authed_client.get("/")
        assert "leo" in response.text

    def test_nav_shows_logout_button(self, authed_client):
        """Given I am logged in
        When I view any page
        Then the nav bar has a logout button
        """
        response = authed_client.get("/")
        assert "logout" in response.text.lower()
```

- [ ] **Step 2: Add test fixtures to conftest.py**

Add `client`, `authed_client`, `seed_user_leo` fixtures that create a TestClient with the FastAPI app, seeded DB, and optionally logged-in session.

- [ ] **Step 3: Write auth.py (session dependency)**

```python
# flat_finder/users/auth.py
import logging
from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger(__name__)

LOGIN_PATH = "/login"
PUBLIC_PATHS = {LOGIN_PATH, "/static"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if any(request.url.path.startswith(p) for p in PUBLIC_PATHS):
            return await call_next(request)
        user_id = request.session.get("user_id")
        if not user_id:
            return RedirectResponse(url=f"{request.app.root_path}{LOGIN_PATH}", status_code=303)
        return await call_next(request)


def get_current_user_id(request: Request) -> int:
    return request.session["user_id"]


def get_current_username(request: Request) -> str:
    return request.session["username"]
```

- [ ] **Step 4: Write auth_routes.py**

```python
# flat_finder/api/auth_routes.py
import logging
from typing import Annotated
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from flat_finder.users.service import UserService

log = logging.getLogger(__name__)
router = APIRouter()

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})

@router.post("/login")
def login(request: Request, username: Annotated[str, Form()]):
    if not username.strip():
        return templates.TemplateResponse(request, "login.html", {"error": "Username required"})
    # UserService injected via Depends — get from request.app.state or dependency
    user = user_service.login(username)
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    log.info("Session created for user: %s", user.username)
    return RedirectResponse(url=request.app.root_path + "/", status_code=303)

@router.post("/logout")
def logout(request: Request):
    username = request.session.get("username", "unknown")
    request.session.clear()
    log.info("User logged out: %s", username)
    return RedirectResponse(url=f"{request.app.root_path}/login", status_code=303)
```

- [ ] **Step 5: Write app.py (FastAPI app with middleware)**

Create `flat_finder/api/app.py`. Configure `SessionMiddleware` with `SECRET_KEY`, register `AuthMiddleware`, mount static files, include all routers. Port the `lifespan` from `ui/main.py` — run Alembic migration on startup instead of `init_db`.

- [ ] **Step 6: Write login.html template**

Minimal centered form, consistent with existing design. Username text input + submit button. Show error message if present. Use Space Grotesk / Outfit fonts, blue accent. Support dark mode.

- [ ] **Step 7: Update base.html**

Port from `ui/templates/base.html`. Add to the nav bar (right side):
- Username display: `{{ request.session.get("username", "") }}`
- Logout form: `<form method="POST" action="{{ url_for('logout') }}"><button type="submit">Logout</button></form>`

- [ ] **Step 8: Run tests**

```bash
uv run pytest tests/test_auth.py -v
```

- [ ] **Step 9: Commit**

```bash
git add flat_finder/users/auth.py flat_finder/api/ flat_finder/templates/ tests/test_auth.py tests/conftest.py
git commit -m "feat: add login/logout with session middleware and auth tests"
```

---

## Task 9: Port routes — feed, detail, map, settings

**Files:**
- Create: `flat_finder/api/feed.py`, `detail.py`, `map_page.py`, `settings.py`
- Create: `flat_finder/api/schemas.py`
- Create: `flat_finder/api/zones_api.py`, `state_api.py`, `listings_api.py`
- Test: `tests/test_feed.py`, `tests/test_detail.py`, `tests/test_settings.py`, `tests/test_zones_api.py`, `tests/test_state_api.py`

Port all routes from `ui/main.py` to individual route files. Each route now gets `user_id` from the session and passes it to services. Zone filtering uses `listing_zones` junction table instead of the `zone` column on listings.

- [ ] **Step 1: Write E2E feed tests**

```python
# tests/test_feed.py
class TestFeedUserScoping:
    """Feature: Per-user feed

    As a user, I only see listings in my zones,
    scored by my POIs, with my seen/favourite state.
    """

    def test_user_sees_only_listings_in_their_zones(self, authed_client, seed_two_users_with_zones):
        """Given Leo has zone A with listing 1, Amelie has zone B with listing 2
        When Leo views the feed
        Then he sees listing 1 but not listing 2
        """
        ...

    def test_zone_filter_shows_user_zones(self, authed_client, seed_user_with_zones):
        """Given Leo has zones "South London" and "East London"
        When Leo views the feed
        Then the zone filter dropdown shows his zones
        """
        ...

    def test_favourite_state_independent(self, authed_client, seed_two_users):
        """Given Leo favourited listing X
        When Amelie views listing X
        Then it is not favourite for her
        """
        ...
```

- [ ] **Step 2: Write E2E settings tests**

```python
# tests/test_settings.py
class TestNtfySettings:
    """Feature: Per-user notification settings"""

    def test_set_ntfy_topic(self, authed_client):
        """Given I am logged in
        When I set my ntfy topic to "my-flat-alerts"
        Then it is saved and displayed on the settings page
        """
        ...

    def test_clear_ntfy_topic(self, authed_client):
        """Given I have a ntfy topic set
        When I clear it
        Then no notifications are sent
        """
        ...

class TestPOIUserScoping:
    """Feature: Per-user POIs"""

    def test_user_only_sees_own_pois(self, authed_client, seed_two_users_with_pois):
        """Given Leo has POI "Office" and Amelie has POI "Gym"
        When Leo views settings
        Then he sees "Office" but not "Gym"
        """
        ...
```

- [ ] **Step 3: Write schemas.py**

Port `StateUpdate`, `ZoneIn` from `ui/main.py`:
```python
# flat_finder/api/schemas.py
from pydantic import BaseModel
from typing import Any

class StateUpdateRequest(BaseModel):
    seen: bool | None = None
    favourite: bool | None = None
    notes: str | None = None
    override_dishwasher: str | None = None
    override_washer: str | None = None
    override_outdoor: str | None = None

class ZoneCreateRequest(BaseModel):
    name: str
    geometry: dict[str, Any]

class NtfyUpdateRequest(BaseModel):
    topic: str | None = None
```

- [ ] **Step 4: Write dependencies.py**

```python
# flat_finder/api/dependencies.py
from collections.abc import Generator
from fastapi import Depends, Request
from sqlalchemy.orm import Session
from flat_finder.database import get_session
from flat_finder.users.auth import get_current_user_id

def get_db(request: Request) -> Generator[Session]:
    session_factory = request.app.state.session_factory
    session = session_factory()
    try:
        yield session
    finally:
        session.close()

def get_user_service(db: Session = Depends(get_db)):
    from flat_finder.users.persistence import UserRepository
    from flat_finder.users.service import UserService
    return UserService(UserRepository(db))

# Similar factories for ListingService, ZoneService, POIService
```

- [ ] **Step 5: Port all route handlers**

Port from `ui/main.py` to individual route files. Each route handler:
1. Gets `user_id` from `Depends(get_current_user_id)`
2. Gets the relevant service from `Depends(get_*_service)`
3. Calls service method
4. Returns template or JSON response

Key changes from the original:
- `_get_feed_data()` now takes `user_id`, queries `listing_zones` for zone filtering
- `_get_detail_data()` now takes `user_id` for user_state
- Settings routes scope POIs/zones to current user
- New `POST /settings/ntfy` route for updating ntfy topic

- [ ] **Step 6: Port remaining templates**

Copy `feed.html`, `detail.html`, `map.html`, `settings.html`, `_macros.html` from `ui/templates/`.

Update `settings.html`: add ntfy topic section at the top:
```html
<section>
  <h2>Notifications</h2>
  <form method="POST" action="{{ url_for('update_ntfy') }}">
    <label for="ntfy_topic">ntfy topic</label>
    <input name="topic" value="{{ current_user.ntfy_topic or '' }}" placeholder="my-flat-alerts">
    <small>Notifications sent to https://ntfy.sh/your-topic</small>
    <button type="submit">Save</button>
  </form>
</section>
```

- [ ] **Step 7: Run all E2E tests**

```bash
uv run pytest tests/test_feed.py tests/test_detail.py tests/test_settings.py tests/test_zones_api.py tests/test_state_api.py -v
```

- [ ] **Step 8: Commit**

```bash
git add flat_finder/api/ flat_finder/templates/ tests/test_feed.py tests/test_detail.py tests/test_settings.py tests/test_zones_api.py tests/test_state_api.py
git commit -m "feat: port all routes with user-scoped queries and per-user settings"
```

---

## Task 10: Port scraper + per-user notifications + listing archive

**Files:**
- Create: `flat_finder/scraper/runner.py`
- Port: `flat_finder/scraper/rightmove.py`, `openrent.py`, `commute.py`, `notifier.py`
- Test: `tests/test_scraper.py`

- [ ] **Step 1: Write scraper tests**

```python
# tests/test_scraper.py
class TestListingZonesPopulation:
    """Feature: Scraper tags listings with zones"""

    def test_new_listing_gets_listing_zone_row(self, ...):
        """Given zone X exists
        When the scraper finds a new listing in zone X
        Then a listing_zones(listing_id, zone_id) row is created
        """
        ...

    def test_deduped_listing_still_gets_zone_link(self, ...):
        """Given listing Y already exists (found via zone A)
        When zone B also covers listing Y
        Then listing_zones gets a row for (Y, zone_B) too
        """
        ...

class TestPerUserNotifications:
    """Feature: Notifications sent per-user"""

    def test_user_with_ntfy_topic_gets_notification(self, ...):
        """Given Leo has ntfy_topic "leo-flats" and new listings in his zones
        When the scraper finishes
        Then ntfy is called with topic "leo-flats" and Leo's listings
        """
        ...

    def test_user_without_topic_gets_no_notification(self, ...):
        """Given Amelie has no ntfy_topic
        When new listings are found in her zones
        Then no ntfy call is made for her
        """
        ...

class TestListingArchival:
    """Feature: Old listings archived, not deleted"""

    def test_old_listings_moved_to_archive(self, ...):
        """Given a listing older than 14 days
        When the scraper prunes
        Then the listing is in listings_archive and removed from listings
        """
        ...

    def test_archived_listing_orphans_cleaned(self, ...):
        """Given a listing is archived
        Then its user_state, poi_commutes, listing_zones rows are removed
        """
        ...
```

- [ ] **Step 2: Port scraper files**

Copy `scraper/rightmove.py`, `openrent.py`, `commute.py`, `notifier.py` to `flat_finder/scraper/`. Update imports from `shared.*` to `flat_finder.*`.

- [ ] **Step 3: Write runner.py**

Port from `scraper/scraper.py` with these changes:
1. Use SQLAlchemy session instead of raw sqlite3
2. After inserting a listing for zone X, call `listing_zone_dao.link(listing_id, zone_id)` (INSERT OR IGNORE)
3. On dedup (listing already exists), still call `listing_zone_dao.link()`
4. After scrape loop, notifications are per-user:
   ```python
   users = user_dao.get_all_with_ntfy()
   for user in users:
       user_zone_ids = [z.id for z in zone_dao.get_by_user(user.id)]
       user_new_listings = [l for l in new_listings
                            if any(zid in listing_zone_map.get(l["id"], set()) for zid in user_zone_ids)]
       if user_new_listings and user.ntfy_topic:
           user_pois = poi_dao.get_by_user(user.id)
           title, body = format_ntfy_message(user_new_listings, user_pois)
           send_ntfy(user.ntfy_topic, title, body, click_url=user_new_listings[0].get("url"))
   ```
5. Archive step replaces delete:
   ```python
   archived = listing_dao.archive_old(PRUNE_AFTER_DAYS)
   if archived:
       listing_state_dao.delete_for_listings(archived_ids)
       poi_commute_dao.delete_for_listings(archived_ids)
       listing_zone_dao.delete_for_listings(archived_ids)
   ```

- [ ] **Step 4: Run scraper tests**

```bash
uv run pytest tests/test_scraper.py -v
```

- [ ] **Step 5: Commit**

```bash
git add flat_finder/scraper/ tests/test_scraper.py
git commit -m "feat: port scraper with listing_zones, per-user notifications, archive"
```

---

## Task 11: Port utilities + remaining tests

**Files:**
- Create: `flat_finder/geo.py`, `flat_finder/scraping.py`, `flat_finder/zone_utils.py`
- Port: `tests/test_geo.py`, `tests/test_commute.py`, `tests/test_notifier.py`, `tests/test_openrent.py`, `tests/test_rightmove.py`, `tests/test_zone_resolution.py`

- [ ] **Step 1: Port shared utilities**

Copy and update imports:
- `shared/geo.py` -> `flat_finder/geo.py`
- `shared/scraping.py` -> `flat_finder/scraping.py`
- `shared/zones.py` -> `flat_finder/zone_utils.py`

- [ ] **Step 2: Port existing tests**

Update all imports in test files from `shared.*` / `scraper.*` / `ui.*` to `flat_finder.*`. Update test fixtures to use SQLAlchemy sessions instead of raw sqlite3.

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest -v
```
All tests must pass.

- [ ] **Step 4: Commit**

```bash
git add flat_finder/geo.py flat_finder/scraping.py flat_finder/zone_utils.py tests/
git commit -m "feat: port shared utilities and update all tests"
```

---

## Task 12: Update build config + CI

**Files:**
- Modify: `pyproject.toml`
- Modify: `docker-compose.yml`
- Move: `ui/Dockerfile` -> `Dockerfile.ui`
- Move: `scraper/Dockerfile` -> `Dockerfile.scraper`
- Modify: `.github/workflows/ci.yml`
- Create: `flat_finder/static/` (copy from `ui/static/`)

- [ ] **Step 1: Update pyproject.toml**

```toml
[tool.ruff]
src = ["flat_finder", "tests"]

[tool.coverage.run]
source = ["flat_finder"]

[tool.hatch.build.targets.wheel]
packages = ["flat_finder"]
```

Add import-linter config:
```toml
[tool.importlinter]
root_packages = ["flat_finder"]

[[tool.importlinter.contracts]]
name = "Domain does not import from API or infrastructure"
type = "forbidden"
source_modules = [
    "flat_finder.listings.model",
    "flat_finder.listings.dao",
    "flat_finder.zones.model",
    "flat_finder.zones.dao",
    "flat_finder.pois.model",
    "flat_finder.pois.dao",
    "flat_finder.users.model",
    "flat_finder.users.dao",
]
forbidden_modules = [
    "flat_finder.api",
    "flat_finder.database",
    "sqlalchemy",
]
```

- [ ] **Step 2: Update Dockerfiles**

`Dockerfile.ui`:
```dockerfile
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY flat_finder/ flat_finder/
COPY alembic/ alembic/
COPY alembic.ini .
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.13-slim
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn flat_finder.api.app:app --host 0.0.0.0 --port 8000"]
```

`Dockerfile.scraper`:
```dockerfile
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY flat_finder/ flat_finder/
COPY alembic/ alembic/
COPY alembic.ini .
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.13-slim
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini
VOLUME /app/data
ENV PATH="/app/.venv/bin:$PATH"
ENV FLAT_FINDER_DB=/app/data/flat_finder.db
CMD ["sh", "-c", "alembic upgrade head && while true; do python -m flat_finder.scraper.runner; sleep 900; done"]
```

- [ ] **Step 3: Update docker-compose.yml**

```yaml
services:
  flat-finder:
    build:
      context: .
      dockerfile: Dockerfile.ui
    environment:
      - FLAT_FINDER_DB=/app/data/flat_finder.db
      - SECRET_KEY=${SECRET_KEY:-change-me-in-production}
    # ... rest unchanged

  flat-finder-scraper:
    build:
      context: .
      dockerfile: Dockerfile.scraper
    environment:
      - FLAT_FINDER_DB=/app/data/flat_finder.db
      - GMAIL_ADDRESS=${GMAIL_ADDRESS:-}
      - GMAIL_APP_PASSWORD=${GMAIL_APP_PASSWORD:-}
    # NTFY_TOPIC removed — now per-user in DB
```

- [ ] **Step 4: Update CI**

```yaml
- run: uv run ruff check flat_finder/ tests/
- run: uv run ruff format --check flat_finder/ tests/
- run: uv run ty check flat_finder/
- run: uv run lint-imports  # import-linter
```

- [ ] **Step 5: Run lint + tests**

```bash
uv run ruff check flat_finder/ tests/
uv run lint-imports
uv run pytest -v --cov
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml docker-compose.yml Dockerfile.ui Dockerfile.scraper .github/ flat_finder/static/
git commit -m "chore: update build config, Dockerfiles, CI for new package structure"
```

---

## Task 13: Delete old code + final cleanup

**Files:**
- Delete: `shared/` directory
- Delete: `scraper/` directory
- Delete: `ui/` directory

- [ ] **Step 1: Verify no imports reference old packages**

```bash
uv run python -c "import flat_finder.api.app; print('OK')"
uv run pytest -v --cov
```
All tests pass, coverage >= 80%.

- [ ] **Step 2: Run import-linter**

```bash
uv run lint-imports
```
All contracts pass.

- [ ] **Step 3: Delete old directories**

```bash
git rm -r shared/ scraper/ ui/
```

- [ ] **Step 4: Final full test run**

```bash
uv run ruff check flat_finder/ tests/
uv run ruff format --check flat_finder/ tests/
uv run lint-imports
uv run pytest -v --cov
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: remove old shared/scraper/ui directories"
```

---

## Task 14: Create PR + Docker build

- [ ] **Step 1: Push branch**

```bash
git push -u origin feat/multi-user
```

- [ ] **Step 2: Build Docker images locally**

```bash
docker compose build
```
Verify both images build successfully.

- [ ] **Step 3: Create PR**

```bash
gh pr create --title "feat: multi-user support + clean architecture restructure" --body "$(cat <<'EOF'
## Summary
- Restructured codebase to Clean Architecture (domain-first folders under `flat_finder/`)
- Added SQLAlchemy 2.0 + Alembic for ORM and migrations
- Added multi-user support: username login, per-user zones/POIs/state
- Per-user ntfy notifications (configurable in settings)
- Listing archive (14-day retention, old listings moved to analytics table)
- import-linter enforces layer contracts in CI

## Test plan
- [ ] Login as "leo" — existing data preserved (zones, POIs, favourites)
- [ ] Login as "amelie" — new user created, empty zones/POIs
- [ ] Create zones/POIs as each user — verify isolation
- [ ] Mark listing as favourite as leo — verify amelie doesn't see it
- [ ] Set ntfy topic in settings — verify notification arrives on next scrape
- [ ] Verify scraper populates listing_zones correctly
- [ ] Verify old listings archived (not deleted) after 14 days
- [ ] Logout and verify redirect to login
- [ ] Docker build and run on Pi
EOF
)"
```

- [ ] **Step 4: Report PR URL**

Share the PR URL for review.
