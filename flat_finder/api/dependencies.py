from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from flat_finder.listings.persistence import ListingRepository, ListingStateRepository
from flat_finder.listings.service import ListingService
from flat_finder.pois.persistence import POICommuteRepository, POIRepository
from flat_finder.pois.service import POIService
from flat_finder.users.persistence import UserRepository
from flat_finder.users.service import UserService
from flat_finder.zones.persistence import ZoneRepository
from flat_finder.zones.service import ZoneService


def get_db(request: Request) -> Generator[Session]:
    session_factory = request.app.state.session_factory
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_current_user_id(request: Request) -> int:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


def get_user_service(db: Annotated[Session, Depends(get_db)]) -> UserService:
    return UserService(UserRepository(db))


def get_zone_service(db: Annotated[Session, Depends(get_db)]) -> ZoneService:
    return ZoneService(ZoneRepository(db))


def get_poi_service(db: Annotated[Session, Depends(get_db)]) -> POIService:
    return POIService(POIRepository(db), POICommuteRepository(db))


def get_listing_service(db: Annotated[Session, Depends(get_db)]) -> ListingService:
    return ListingService(
        ListingRepository(db),
        ListingStateRepository(db),
        POICommuteRepository(db),
    )
