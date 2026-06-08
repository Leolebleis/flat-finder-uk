from sqlalchemy import text
from flat_finder.database import Base, get_engine, get_session


class TestDatabaseEngine:
    """Feature: Database connectivity

    As the application, I can connect to SQLite
    so that all components share a single DB.
    """

    def test_engine_connects_to_sqlite(self, tmp_path):
        """Given a path to a SQLite file
        When I create an engine
        Then I can execute queries
        """
        db_path = tmp_path / "test.db"
        engine = get_engine(db_path)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

    def test_session_factory_returns_working_session(self, tmp_path):
        """Given a database engine
        When I create a session
        Then I can use it to query the database
        """
        db_path = tmp_path / "test.db"
        engine = get_engine(db_path)
        Base.metadata.create_all(engine)
        session = get_session(engine)
        with session() as s:
            result = s.execute(text("SELECT 1"))
            assert result.scalar() == 1

    def test_engine_uses_wal_mode(self, tmp_path):
        """Given a new engine
        When I check the journal mode
        Then it is WAL (for concurrent access)
        """
        db_path = tmp_path / "test.db"
        engine = get_engine(db_path)
        with engine.connect() as conn:
            mode = conn.execute(text("PRAGMA journal_mode")).scalar()
            assert mode == "wal"
