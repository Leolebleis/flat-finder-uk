from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: int
    username: str
    ntfy_topic: str | None
    created_at: str
