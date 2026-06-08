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
