import pytest
from flat_finder.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def db_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine) -> Session:
    factory = sessionmaker(bind=db_engine)
    session = factory()
    yield session
    session.close()
