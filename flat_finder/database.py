import logging
from pathlib import Path
from typing import Protocol

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, sessionmaker

log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class _HasListingId(Protocol):
    listing_id: Mapped[str]


def delete_by_listing_ids(session: Session, model: type[_HasListingId], listing_ids: list[str]) -> None:
    """Bulk-delete rows of `model` whose listing_id is in listing_ids."""
    if listing_ids:
        session.query(model).filter(model.listing_id.in_(listing_ids)).delete(synchronize_session="fetch")
        session.flush()


def _set_sqlite_pragmas(dbapi_conn: object, _connection_record: object) -> None:
    cursor = dbapi_conn.cursor()  # ty: ignore[unresolved-attribute]
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
