import logging
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def _set_sqlite_pragmas(dbapi_conn: object, _connection_record: object) -> None:
    cursor = dbapi_conn.cursor()  # type: ignore[union-attr]
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
