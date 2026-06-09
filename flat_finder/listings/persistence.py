import datetime as dt
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, Text, exc
from sqlalchemy.orm import Mapped, Session, mapped_column

from flat_finder.database import Base
from flat_finder.listings.model import Listing, ListingState
from flat_finder.zones.persistence import ListingZoneDB

log = logging.getLogger(__name__)


class ListingDB(Base):
    __tablename__ = "listings"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    property_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    furnishing: Mapped[str | None] = mapped_column(Text, nullable=True)
    outdoor_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    listing_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_pcm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sqft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    has_dishwasher: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    has_washer: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    has_outdoor: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    zone: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ListingStateDB(Base):
    __tablename__ = "user_state"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[str] = mapped_column(Text, primary_key=True)
    seen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    favourite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_dishwasher: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_washer: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_outdoor: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ListingArchiveDB(Base):
    __tablename__ = "listings_archive"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    property_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    furnishing: Mapped[str | None] = mapped_column(Text, nullable=True)
    outdoor_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    listing_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_pcm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sqft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    has_dishwasher: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    has_washer: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    has_outdoor: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    zone: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ScraperStateDB(Base):
    __tablename__ = "scraper_state"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


_LISTING_FIELDS = (
    "id",
    "source",
    "url",
    "title",
    "address",
    "description",
    "image_url",
    "property_type",
    "furnishing",
    "outdoor_type",
    "listing_date",
    "price_pcm",
    "bedrooms",
    "sqft",
    "latitude",
    "longitude",
    "has_dishwasher",
    "has_washer",
    "has_outdoor",
    "zone",
    "first_seen",
)


class ListingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _coerce_first_seen(value: object) -> datetime:
        """Convert first_seen to a naive datetime (UTC) for storage."""
        if isinstance(value, datetime):
            return value.replace(tzinfo=None) if value.tzinfo else value
        if isinstance(value, str):
            dt = datetime.fromisoformat(value)
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        return datetime.now(UTC).replace(tzinfo=None)

    def insert(self, listing: dict[str, Any]) -> bool:
        """Insert a listing from scraper dict format. Returns True if new, False if duplicate."""
        db_listing = ListingDB(
            id=listing["id"],
            source=listing.get("source", ""),
            url=listing.get("url", ""),
            title=listing.get("title"),
            address=listing.get("address"),
            description=listing.get("description"),
            image_url=listing.get("image_url"),
            property_type=listing.get("property_type"),
            furnishing=listing.get("furnishing"),
            outdoor_type=listing.get("outdoor_type"),
            listing_date=listing.get("listing_date"),
            price_pcm=listing.get("price_pcm"),
            bedrooms=listing.get("bedrooms"),
            sqft=listing.get("sqft"),
            latitude=listing.get("latitude"),
            longitude=listing.get("longitude"),
            has_dishwasher=listing.get("has_dishwasher", "unknown"),
            has_washer=listing.get("has_washer", "unknown"),
            has_outdoor=listing.get("has_outdoor", "unknown"),
            zone=listing.get("zone"),
            first_seen=self._coerce_first_seen(listing.get("first_seen")),
        )
        try:
            with self._session.begin_nested():
                self._session.add(db_listing)
            log.info("Inserted listing: %s", listing["id"])
        except exc.IntegrityError:
            return False
        else:
            return True

    def get_all_with_state(self, user_id: int, zone_ids: list[int]) -> list[dict[str, Any]]:
        """Return listings in the given zones JOINed with user state for user_id."""
        if not zone_ids:
            return []

        listing_ids_in_zones = (
            self._session.query(ListingZoneDB.listing_id).filter(ListingZoneDB.zone_id.in_(zone_ids)).scalar_subquery()
        )

        rows = (
            self._session.query(ListingDB, ListingStateDB)
            .outerjoin(
                ListingStateDB,
                (ListingStateDB.listing_id == ListingDB.id) & (ListingStateDB.user_id == user_id),
            )
            .filter(ListingDB.id.in_(listing_ids_in_zones))
            .all()
        )

        result = []
        for listing_row, state_row in rows:
            d = self._listing_to_dict(listing_row)
            if state_row:
                d.update(
                    seen=state_row.seen,
                    favourite=state_row.favourite,
                    notes=state_row.notes,
                    override_dishwasher=state_row.override_dishwasher,
                    override_washer=state_row.override_washer,
                    override_outdoor=state_row.override_outdoor,
                    updated_at=state_row.updated_at,
                )
            else:
                d.update(
                    seen=False,
                    favourite=False,
                    notes=None,
                    override_dishwasher=None,
                    override_washer=None,
                    override_outdoor=None,
                    updated_at=None,
                )
            result.append(d)
        return result

    def get_by_id(self, listing_id: str) -> Listing | None:
        row = self._session.get(ListingDB, listing_id)
        return self._to_domain(row) if row else None

    def get_listings_in_zone_polygon(self, geometry_geojson: str) -> list[Listing]:  # noqa: ARG002
        """Return all listings with lat/lng (polygon check done in Python with shapely)."""
        rows = (
            self._session.query(ListingDB).filter(ListingDB.latitude.isnot(None), ListingDB.longitude.isnot(None)).all()
        )
        return [self._to_domain(r) for r in rows]

    def archive_old(self, days: int) -> list[str]:
        """Move listings older than `days` to archive table. Returns list of archived IDs."""
        cutoff = datetime.now(UTC).replace(tzinfo=None) - dt.timedelta(days=days)

        old_rows = self._session.query(ListingDB).filter(ListingDB.first_seen < cutoff).all()
        archived_ids = [row.id for row in old_rows]
        for row in old_rows:
            archive = ListingArchiveDB(**{f: getattr(row, f) for f in _LISTING_FIELDS})
            self._session.add(archive)
            self._session.delete(row)

        if archived_ids:
            self._session.flush()
            log.info("Archived %d old listings", len(archived_ids))
        return archived_ids

    @staticmethod
    def _to_domain(row: ListingDB) -> Listing:
        first_seen = row.first_seen
        first_seen_str = first_seen.isoformat() if isinstance(first_seen, datetime) else str(first_seen)
        return Listing(
            id=row.id,
            source=row.source,
            url=row.url,
            title=row.title,
            price_pcm=row.price_pcm,
            bedrooms=row.bedrooms,
            address=row.address,
            latitude=row.latitude,
            longitude=row.longitude,
            description=row.description,
            image_url=row.image_url,
            property_type=row.property_type,
            furnishing=row.furnishing,
            sqft=row.sqft,
            has_dishwasher=row.has_dishwasher,
            has_washer=row.has_washer,
            has_outdoor=row.has_outdoor,
            outdoor_type=row.outdoor_type,
            zone=row.zone,
            first_seen=first_seen_str,
            listing_date=row.listing_date,
        )

    @staticmethod
    def _listing_to_dict(row: ListingDB) -> dict[str, Any]:
        first_seen = row.first_seen
        first_seen_str = first_seen.isoformat() if isinstance(first_seen, datetime) else str(first_seen)
        return {
            "id": row.id,
            "source": row.source,
            "url": row.url,
            "title": row.title,
            "address": row.address,
            "description": row.description,
            "image_url": row.image_url,
            "property_type": row.property_type,
            "furnishing": row.furnishing,
            "outdoor_type": row.outdoor_type,
            "listing_date": row.listing_date,
            "price_pcm": row.price_pcm,
            "bedrooms": row.bedrooms,
            "sqft": row.sqft,
            "latitude": row.latitude,
            "longitude": row.longitude,
            "has_dishwasher": row.has_dishwasher,
            "has_washer": row.has_washer,
            "has_outdoor": row.has_outdoor,
            "zone": row.zone,
            "first_seen": first_seen_str,
        }


class ListingStateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: int, listing_id: str) -> ListingState | None:
        row = self._session.get(ListingStateDB, (user_id, listing_id))
        return self._to_domain(row) if row else None

    def upsert(self, user_id: int, listing_id: str, updates: dict[str, Any]) -> ListingState:
        """Insert or update user state. Only keys present in updates are applied."""
        row = self._session.get(ListingStateDB, (user_id, listing_id))
        if row is None:
            row = ListingStateDB(
                user_id=user_id,
                listing_id=listing_id,
                seen=False,
                favourite=False,
                notes=None,
                override_dishwasher=None,
                override_washer=None,
                override_outdoor=None,
                updated_at=None,
            )
            self._session.add(row)

        for key, value in updates.items():
            if hasattr(row, key):
                setattr(row, key, value)
        row.updated_at = datetime.now(UTC).replace(tzinfo=None)
        self._session.flush()
        return self._to_domain(row)

    def delete_for_listings(self, listing_ids: list[str]) -> None:
        if listing_ids:
            self._session.query(ListingStateDB).filter(ListingStateDB.listing_id.in_(listing_ids)).delete(
                synchronize_session="fetch"
            )
            self._session.flush()

    @staticmethod
    def _to_domain(row: ListingStateDB) -> ListingState:
        updated_at = row.updated_at
        updated_at_str = updated_at.isoformat() if isinstance(updated_at, datetime) else None
        return ListingState(
            user_id=row.user_id,
            listing_id=row.listing_id,
            seen=row.seen,
            favourite=row.favourite,
            notes=row.notes,
            override_dishwasher=row.override_dishwasher,
            override_washer=row.override_washer,
            override_outdoor=row.override_outdoor,
            updated_at=updated_at_str,
        )
