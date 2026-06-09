import logging

from flat_finder.users.dao import UserDAO
from flat_finder.users.model import User

log = logging.getLogger(__name__)


class UserService:
    def __init__(self, user_dao: UserDAO) -> None:
        self._dao = user_dao

    def login(self, username: str) -> User:
        """Login or auto-create user. Normalizes username (strip + lowercase)."""
        normalized = username.strip().lower()
        user = self._dao.get_by_username(normalized)
        if user:
            log.info("User logged in: %s", user.username)
            return user
        user = self._dao.create(normalized)
        log.info("New user created: %s", user.username)
        return user

    def get_by_id(self, user_id: int) -> User | None:
        return self._dao.get_by_id(user_id)

    def update_ntfy_topic(self, user_id: int, topic: str | None) -> None:
        clean = topic.strip() if topic else None
        clean = clean or None
        self._dao.update_ntfy_topic(user_id, clean)
        log.info("Updated ntfy topic for user %d", user_id)

    def update_search_params(
        self, user_id: int, max_rent_pcm: int | None, min_bedrooms: int | None, max_bedrooms: int | None
    ) -> None:
        self._dao.update_search_params(user_id, max_rent_pcm, min_bedrooms, max_bedrooms)
        log.info(
            "Updated search params for user %d: rent=%s beds=%s-%s",
            user_id, max_rent_pcm, min_bedrooms, max_bedrooms,
        )
