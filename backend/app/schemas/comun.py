from typing import Annotated, Generic, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Pagina(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


PASSWORD_MIN = 8


def validar_password(valor: str) -> str:
    if len(valor) < PASSWORD_MIN:
        raise ValueError(f"La contraseña debe tener al menos {PASSWORD_MIN} caracteres")
    if len(valor.encode("utf-8")) > 72:
        raise ValueError("La contraseña no puede exceder 72 bytes")
    if not any(c.isalpha() for c in valor) or not any(c.isdigit() for c in valor):
        raise ValueError("La contraseña debe contener letras y números")
    return valor


Password = Annotated[str, Field(max_length=72), AfterValidator(validar_password)]
TextoCorto = Annotated[str, Field(min_length=1, max_length=255)]
