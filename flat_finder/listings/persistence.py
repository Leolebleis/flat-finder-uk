from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from flat_finder.database import Base


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
