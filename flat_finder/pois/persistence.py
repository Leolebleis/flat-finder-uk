from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from flat_finder.database import Base


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
