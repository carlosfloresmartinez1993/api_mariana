import uuid
from datetime import datetime
from typing import Any

from app.models.enums import AccionBitacora
from app.schemas.comun import ORMModel


class BitacoraOut(ORMModel):
    id: uuid.UUID
    fecha: datetime
    usuario_id: uuid.UUID | None
    usuario_nombre: str
    entidad: str
    entidad_id: uuid.UUID | None
    accion: AccionBitacora
    detalle: dict[str, Any]
