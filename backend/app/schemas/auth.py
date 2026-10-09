from pydantic import BaseModel

from app.schemas.comun import Password


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class CambioPassword(BaseModel):
    actual: str
    nueva: Password
