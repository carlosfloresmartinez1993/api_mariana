import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AccionBitacora, Bitacora
from app.services.serializacion import a_json


def registrar(
    db: Session,
    *,
    usuario_id: uuid.UUID | None,
    entidad: str,
    entidad_id: uuid.UUID | None,
    accion: AccionBitacora,
    detalle: dict[str, Any] | None = None,
) -> Bitacora:
    """Agrega un registro a la bitácora dentro de la transacción actual.

    Se confirma junto con el cambio que documenta: si el cambio falla,
    tampoco queda el registro, y viceversa.
    """
    registro = Bitacora(
        usuario_id=usuario_id,
        entidad=entidad,
        entidad_id=entidad_id,
        accion=accion,
        detalle=a_json(detalle or {}),
    )
    db.add(registro)
    return registro


def instantanea(obj: Any, campos: tuple[str, ...]) -> dict[str, Any]:
    return a_json({campo: getattr(obj, campo) for campo in campos})
