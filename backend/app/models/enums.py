from enum import StrEnum

from sqlalchemy import Enum as SAEnum


class Rol(StrEnum):
    SUPERUSUARIO = "superusuario"
    ADMIN = "admin"
    CONTADOR = "contador"


class AccionBitacora(StrEnum):
    """Catálogo cerrado de acciones de la bitácora. La entidad afectada va en su propia columna."""

    INICIO_SESION = "INICIO_SESION"
    INICIO_SESION_FALLIDO = "INICIO_SESION_FALLIDO"
    CAMBIO_PASSWORD = "CAMBIO_PASSWORD"
    CREAR = "CREAR"
    EDITAR = "EDITAR"
    ACTIVAR = "ACTIVAR"
    DESACTIVAR = "DESACTIVAR"
    ANULAR = "ANULAR"


def enum_columna(enum_cls: type[StrEnum], nombre: str, largo: int) -> SAEnum:
    """Enum guardado como varchar + CHECK (evita ALTER TYPE al agregar valores)."""
    return SAEnum(
        enum_cls,
        name=nombre,
        native_enum=False,
        create_constraint=True,
        length=largo,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )
