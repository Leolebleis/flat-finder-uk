from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str


class LoginResponse(BaseModel):
    username: str
    user_id: int
