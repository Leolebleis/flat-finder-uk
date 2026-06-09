import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from flat_finder.database import Base
from flat_finder.listings.persistence import ListingDB
from flat_finder.pois.model import POI, POICommute

log = logging.getLogger(__name__)


class POIDB(Base):
    __tablename__ = "pois"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    lat: Mapped[float] = mapped_column(nullable=False)
    lng: Mapped[float] = mapped_column(nullable=False)
    color_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class POICommuteDB(Base):
    __tablename__ = "poi_commutes"

    listing_id: Mapped[str] = mapped_column(Text, primary_key=True)
    poi_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commute_mins: Mapped[int] = mapped_column(Integer, nullable=False)


class POIRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_user(self, user_id: int) -> list[POI]:
        rows = self._session.query(POIDB).filter_by(user_id=user_id).all()
        return [self._to_domain(r) for r in rows]

    def get_all(self) -> list[POI]:
        rows = self._session.query(POIDB).all()
        return [self._to_domain(r) for r in rows]

    def create(self, user_id: int, name: str, lat: float, lng: float, color_index: int) -> POI:
        db_poi = POIDB(
            user_id=user_id,
            name=name,
            lat=lat,
            lng=lng,
            color_index=color_index,
            created_at=datetime.now(UTC).isoformat(),
        )
        self._session.add(db_poi)
        self._session.flush()
        log.info("Created POI: %s (id=%d)", name, db_poi.id)
        return self._to_domain(db_poi)

    def delete(self, poi_id: int) -> None:
        """Delete POI and cascade-delete associated poi_commutes."""
        self._session.query(POICommuteDB).filter_by(poi_id=poi_id).delete(synchronize_session="fetch")
        row = self._session.get(POIDB, poi_id)
        if row:
            self._session.delete(row)
            self._session.flush()

    @staticmethod
    def _to_domain(row: POIDB) -> POI:
        return POI(
            id=row.id,
            user_id=row.user_id,
            name=row.name,
            lat=row.lat,
            lng=row.lng,
            color_index=row.color_index,
            created_at=row.created_at,
        )


class POICommuteRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, listing_id: str, poi_id: int, commute_mins: int) -> None:
        row = self._session.get(POICommuteDB, (listing_id, poi_id))
        if row is None:
            row = POICommuteDB(listing_id=listing_id, poi_id=poi_id, commute_mins=commute_mins)
            self._session.add(row)
        else:
            row.commute_mins = commute_mins
        self._session.flush()

    def get_for_listings(self, listing_ids: list[str]) -> dict[str, dict[int, int]]:
        """Return {listing_id: {poi_id: commute_mins}} for the given listing IDs."""
        if not listing_ids:
            return {}
        rows = self._session.query(POICommuteDB).filter(POICommuteDB.listing_id.in_(listing_ids)).all()
        result: dict[str, dict[int, int]] = {}
        for row in rows:
            result.setdefault(row.listing_id, {})[row.poi_id] = row.commute_mins
        return result

    def get_listings_missing_poi(self, poi_id: int) -> list[dict[str, Any]]:
        """Return listings with lat/lng that do not yet have a commute for poi_id."""
        existing_ids = self._session.query(POICommuteDB.listing_id).filter_by(poi_id=poi_id).scalar_subquery()
        rows = (
            self._session.query(ListingDB)
            .filter(
                ListingDB.latitude.isnot(None),
                ListingDB.longitude.isnot(None),
                ListingDB.id.notin_(existing_ids),
            )
            .all()
        )
        return [{"id": r.id, "latitude": r.latitude, "longitude": r.longitude} for r in rows]

    def delete_for_listings(self, listing_ids: list[str]) -> None:
        if listing_ids:
            self._session.query(POICommuteDB).filter(POICommuteDB.listing_id.in_(listing_ids)).delete(
                synchronize_session="fetch"
            )
            self._session.flush()

    @staticmethod
    def _to_domain(row: POICommuteDB) -> POICommute:
        return POICommute(
            listing_id=row.listing_id,
            poi_id=row.poi_id,
            commute_mins=row.commute_mins,
        )
