from decimal import Decimal
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


def _limpiar(valor: str) -> str:
    valor = " ".join(valor.split())
    if not valor:
        raise ValueError("No puede estar vacío")
    return valor


def _opcional(valor: str | None) -> str | None:
    if valor is None:
        return None
    return " ".join(valor.split()) or None


Password = Annotated[str, Field(max_length=72), AfterValidator(validar_password)]
# Texto obligatorio: se quitan espacios sobrantes y no puede quedar vacío.
Texto = Annotated[str, Field(max_length=255), AfterValidator(_limpiar)]
Nombre200 = Annotated[str, Field(max_length=200), AfterValidator(_limpiar)]
Nombre100 = Annotated[str, Field(max_length=100), AfterValidator(_limpiar)]
# Texto opcional: vacío se guarda como nulo.
TextoOpcional = Annotated[str | None, Field(max_length=255), AfterValidator(_opcional)]
Motivo = Annotated[str, Field(min_length=3, max_length=500), AfterValidator(_limpiar)]


def _centavos(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"))


# Siempre con 2 decimales ("5000" → 5000.00), igual que lo devuelve la base de datos.
Dinero = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2), AfterValidator(_centavos)]
DineroNoNegativo = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2), AfterValidator(_centavos)]
Porcentaje = Annotated[Decimal, Field(ge=0, lt=100, max_digits=5, decimal_places=2), AfterValidator(_centavos)]


class ConMotivo(BaseModel):
    motivo: Motivo
