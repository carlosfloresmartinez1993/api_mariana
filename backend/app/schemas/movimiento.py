import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import Forma, Moneda
from app.schemas.comun import Dinero, Porcentaje, Texto, TextoOpcional
from app.schemas.empresa import Registro


class Factura(BaseModel):
    requiere_factura: bool
    factura_nombre: str | None
    factura_tipo: str | None
    factura_tamano: int | None
    factura_subida_en: datetime | None


class Anulacion(BaseModel):
    anulado: bool
    motivo_anulacion: str | None
    anulado_por: uuid.UUID | None
    fecha_anulacion: datetime | None


# ------------------------------------------------------------------ entradas
class EntradaCrear(BaseModel):
    proyecto_id: uuid.UUID
    empresa_id: uuid.UUID
    cuenta_id: uuid.UUID
    fecha: date
    forma: Forma
    monto: Dinero
    porcentaje_gasto: Porcentaje = Decimal("0")
    concepto: TextoOpcional = None
    referencia: TextoOpcional = Field(default=None, max_length=100)
    requiere_factura: bool = False
    categoria_id: uuid.UUID | None = None


class EntradaActualizar(BaseModel):
    """Proyecto, empresa y cuenta no se cambian: para eso se anula y se vuelve a capturar."""

    fecha: date | None = None
    monto: Dinero | None = None
    porcentaje_gasto: Porcentaje | None = None
    concepto: TextoOpcional = None
    referencia: TextoOpcional = Field(default=None, max_length=100)
    requiere_factura: bool | None = None
    categoria_id: uuid.UUID | None = None


class EntradaOut(Registro, Anulacion, Factura):
    id: uuid.UUID
    categoria_id: uuid.UUID | None
    categoria_nombre: str | None
    proyecto_id: uuid.UUID
    proyecto_nombre: str
    empresa_id: uuid.UUID
    empresa_nombre: str
    cuenta_id: uuid.UUID
    cuenta_nombre: str
    moneda: Moneda
    fecha: date
    forma: Forma
    monto: Decimal
    porcentaje_gasto: Decimal
    monto_gasto: Decimal
    monto_neto: Decimal
    concepto: str | None
    referencia: str | None


# ------------------------------------------------------------------ salidas
class SalidaCrear(BaseModel):
    proyecto_id: uuid.UUID
    empresa_id: uuid.UUID
    cuenta_id: uuid.UUID
    fecha: date
    forma: Forma
    monto: Dinero
    concepto: Texto
    beneficiario: TextoOpcional = Field(default=None, max_length=200)
    requiere_factura: bool = False
    categoria_id: uuid.UUID | None = None


class SalidaActualizar(BaseModel):
    fecha: date | None = None
    monto: Dinero | None = None
    concepto: Texto | None = None
    beneficiario: TextoOpcional = Field(default=None, max_length=200)
    requiere_factura: bool | None = None
    categoria_id: uuid.UUID | None = None


class SalidaOut(Registro, Anulacion, Factura):
    id: uuid.UUID
    categoria_id: uuid.UUID | None
    categoria_nombre: str | None
    proyecto_id: uuid.UUID
    proyecto_nombre: str
    empresa_id: uuid.UUID
    empresa_nombre: str
    cuenta_id: uuid.UUID
    cuenta_nombre: str
    moneda: Moneda
    fecha: date
    forma: Forma
    monto: Decimal
    concepto: str
    beneficiario: str | None

