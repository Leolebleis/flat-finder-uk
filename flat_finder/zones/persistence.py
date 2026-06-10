import logging
from datetime import UTC, datetime

from sqlalchemy import Integer, Text, exc
from sqlalchemy.orm import Mapped, Session, mapped_column

from flat_finder.database import Base, delete_by_listing_ids
from flat_finder.zones.model import Zone

log = logging.getLogger(__name__)


class ZoneDB(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    geometry: Mapped[str] = mapped_column(Text, nullable=False)
    centroid_lat: Mapped[float] = mapped_column(nullable=False)
    centroid_lng: Mapped[float] = mapped_column(nullable=False)
    covering_radius_km: Mapped[float] = mapped_column(nullable=False)
    rightmove_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    openrent_term: Mapped[str | None] = mapped_column(Text, nullable=True)
    color_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class ListingZoneDB(Base):
    __tablename__ = "listing_zones"

    listing_id: Mapped[str] = mapped_column(Text, primary_key=True)
    zone_id: Mapped[int] = mapped_column(Integer, primary_key=True)


class ZoneRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_user(self, user_id: int) -> list[Zone]:
        rows = self._session.query(ZoneDB).filter_by(user_id=user_id).all()
        return [self._to_domain(r) for r in rows]

    def get_all(self) -> list[Zone]:
        rows = self._session.query(ZoneDB).all()
        return [self._to_domain(r) for r in rows]

    def get_by_id(self, zone_id: int) -> Zone | None:
        row = self._session.get(ZoneDB, zone_id)
        return self._to_domain(row) if row else None

    def create(  # noqa: PLR0913
        self,
        user_id: int,
        name: str,
        geometry: str,
        centroid_lat: float,
        centroid_lng: float,
        covering_radius_km: float,
        rightmove_id: str | None,
        openrent_term: str | None,
        color_index: int,
    ) -> Zone:
        db_zone = ZoneDB(
            user_id=user_id,
            name=name,
            geometry=geometry,
            centroid_lat=centroid_lat,
            centroid_lng=centroid_lng,
            covering_radius_km=covering_radius_km,
            rightmove_id=rightmove_id,
            openrent_term=openrent_term,
            color_index=color_index,
            created_at=datetime.now(UTC).isoformat(),
        )
        self._session.add(db_zone)
        self._session.flush()
        log.info("Created zone: %s (id=%d)", name, db_zone.id)
        return self._to_domain(db_zone)

    def update(self, zone_id: int, **kwargs: object) -> None:
        row = self._session.get(ZoneDB, zone_id)
        if row:
            for key, value in kwargs.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            self._session.flush()

    def delete(self, zone_id: int) -> None:
        row = self._session.get(ZoneDB, zone_id)
        if row:
            self._session.delete(row)
            self._session.flush()

    @staticmethod
    def _to_domain(row: ZoneDB) -> Zone:
        return Zone(
            id=row.id,
            user_id=row.user_id,
            name=row.name,
            geometry=row.geometry,
            centroid_lat=row.centroid_lat,
            centroid_lng=row.centroid_lng,
            covering_radius_km=row.covering_radius_km,
            rightmove_id=row.rightmove_id,
            openrent_term=row.openrent_term,
            color_index=row.color_index,
            created_at=row.created_at,
        )


class ListingZoneRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def link(self, listing_id: str, zone_id: int) -> None:
        """INSERT OR IGNORE — silently skip if already linked."""
        try:
            with self._session.begin_nested():
                db_lz = ListingZoneDB(listing_id=listing_id, zone_id=zone_id)
                self._session.add(db_lz)
        except exc.IntegrityError:
            pass  # duplicate — already linked, session savepoint rolls back automatically

    def get_zone_ids_for_listing(self, listing_id: str) -> list[int]:
        rows = self._session.query(ListingZoneDB).filter_by(listing_id=listing_id).all()
        return [r.zone_id for r in rows]

    def get_listing_ids_for_zones(self, zone_ids: list[int]) -> list[str]:
        if not zone_ids:
            return []
        rows = self._session.query(ListingZoneDB).filter(ListingZoneDB.zone_id.in_(zone_ids)).all()
        return list({r.listing_id for r in rows})

    def delete_for_listings(self, listing_ids: list[str]) -> None:
        delete_by_listing_ids(self._session, ListingZoneDB, listing_ids)
