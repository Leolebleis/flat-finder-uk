from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from flat_finder.database import Base


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
