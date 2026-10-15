import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import Moneda, TipoPendiente
from app.schemas.comun import Dinero, Texto, TextoOpcional
from app.schemas.empresa import Registro


class PendienteCrear(BaseModel):
    tipo: TipoPendiente
    concepto: Texto
    contraparte: TextoOpcional = Field(default=None, max_length=200)
    moneda: Moneda
    monto: Dinero
    fecha_vencimiento: date | None = None
    nota: TextoOpcional = Field(default=None, max_length=2000)


class PendienteActualizar(BaseModel):
    """El proyecto no se cambia. Para liquidar: `liquidada=true` y, opcional, `fecha_liquidacion`."""

    tipo: TipoPendiente | None = None
    concepto: Texto | None = None
    contraparte: TextoOpcional = Field(default=None, max_length=200)
    moneda: Moneda | None = None
    monto: Dinero | None = None
    fecha_vencimiento: date | None = None
    nota: TextoOpcional = Field(default=None, max_length=2000)
    liquidada: bool | None = None
    fecha_liquidacion: date | None = None

    @model_validator(mode="after")
    def _coherente(self) -> "PendienteActualizar":
        if self.liquidada is False and self.fecha_liquidacion:
            raise ValueError("Una partida pendiente no lleva fecha de liquidación")
        return self


class PendienteOut(Registro):
    id: uuid.UUID
    proyecto_id: uuid.UUID
    proyecto_nombre: str
    tipo: TipoPendiente
    concepto: str
    contraparte: str | None
    moneda: Moneda
    monto: Decimal
    fecha_vencimiento: date | None
    liquidada: bool
    fecha_liquidacion: date | None
    nota: str | None
    vencida: bool
