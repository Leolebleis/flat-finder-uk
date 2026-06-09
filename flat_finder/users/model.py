from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: int
    username: str
    ntfy_topic: str | None
    max_rent_pcm: int | None
    min_bedrooms: int | None
    max_bedrooms: int | None
    created_at: str
