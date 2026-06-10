import logging
import secrets
from datetime import UTC, datetime

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from flat_finder import config
from flat_finder.database import Base
from flat_finder.users.model import User

log = logging.getLogger(__name__)


class UserDB(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    ntfy_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_rent_pcm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, username: str) -> User:
        db_user = UserDB(
            username=username,
            ntfy_topic=f"flat-finder-{secrets.token_hex(4)}",
            max_rent_pcm=config.MAX_RENT_PCM,
            created_at=datetime.now(UTC).isoformat(),
        )
        self._session.add(db_user)
        self._session.flush()
        log.info("Created user: %s (id=%d)", username, db_user.id)
        return self._to_domain(db_user)

    def get_by_username(self, username: str) -> User | None:
        row = self._session.query(UserDB).filter_by(username=username).first()
        return self._to_domain(row) if row else None

    def get_by_id(self, user_id: int) -> User | None:
        row = self._session.get(UserDB, user_id)
        return self._to_domain(row) if row else None

    def update_ntfy_topic(self, user_id: int, topic: str | None) -> None:
        row = self._session.get(UserDB, user_id)
        if row:
            row.ntfy_topic = topic
            self._session.flush()

    def update_search_params(
        self, user_id: int, max_rent_pcm: int | None, min_bedrooms: int | None, max_bedrooms: int | None
    ) -> None:
        row = self._session.get(UserDB, user_id)
        if row:
            row.max_rent_pcm = max_rent_pcm
            row.min_bedrooms = min_bedrooms
            row.max_bedrooms = max_bedrooms
            self._session.flush()

    def get_all(self) -> list[User]:
        rows = self._session.query(UserDB).all()
        return [self._to_domain(r) for r in rows]

    def get_all_with_ntfy(self) -> list[User]:
        rows = self._session.query(UserDB).filter(UserDB.ntfy_topic.isnot(None)).all()
        return [self._to_domain(r) for r in rows]

    @staticmethod
    def _to_domain(row: UserDB) -> User:
        return User(
            id=row.id,
            username=row.username,
            ntfy_topic=row.ntfy_topic,
            max_rent_pcm=row.max_rent_pcm,
            min_bedrooms=row.min_bedrooms,
            max_bedrooms=row.max_bedrooms,
            created_at=row.created_at,
        )
