from typing import Any

from pydantic import BaseModel


class StateUpdateRequest(BaseModel):
    seen: bool | None = None
    favourite: bool | None = None
    notes: str | None = None
    override_dishwasher: str | None = None
    override_washer: str | None = None
    override_outdoor: str | None = None


class ZoneCreateRequest(BaseModel):
    name: str
    geometry: dict[str, Any]
