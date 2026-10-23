import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import Moneda, TipoCuenta, TipoEstimado
from app.schemas.comun import Dinero, DineroNoNegativo, Nombre100, Nombre200, ORMModel, TextoOpcional


class Registro(ORMModel):
    creado_por: uuid.UUID
    creado_por_nombre: str
    fecha_creacion: datetime


# ------------------------------------------------------------------ empresas
class EmpresaCrear(BaseModel):
    nombre: Nombre200


class EmpresaActualizar(BaseModel):
    nombre: Nombre200


class EmpresaOut(Registro):
    id: uuid.UUID
    nombre: str
    activa: bool


class SaldoMoneda(BaseModel):
    moneda: Moneda
    saldo: Decimal


class EmpresaResumen(EmpresaOut):
    num_cuentas: int
    num_proyectos: int
    saldos: list[SaldoMoneda]


# ------------------------------------------------------------------ cuentas
class CuentaCrear(BaseModel):
    empresa_id: uuid.UUID
    tipo: TipoCuenta
    moneda: Moneda
    # Si se omite: "Caja MXN", "Caja USD" o el nombre del banco.
    nombre: Nombre100 | None = None
    banco: TextoOpcional = Field(default=None, max_length=100)
    numero: TextoOpcional = Field(default=None, max_length=30)


class CuentaActualizar(BaseModel):
    """La empresa, el tipo y la moneda no se pueden cambiar."""

    nombre: Nombre100 | None = None
    banco: TextoOpcional = Field(default=None, max_length=100)
    numero: TextoOpcional = Field(default=None, max_length=30)


class CuentaOut(Registro):
    id: uuid.UUID
    empresa_id: uuid.UUID
    empresa_nombre: str
    tipo: TipoCuenta
    moneda: Moneda
    nombre: str
    banco: str | None
    numero: str | None
    activa: bool


class CuentaConSaldo(CuentaOut):
    saldo: Decimal


# ------------------------------------------------------------------ proyectos
class Proyeccion(BaseModel):
    """Estimados opcionales del proyecto. No afectan saldos: solo se comparan con lo real."""

    estimado_ingresos_mxn: DineroNoNegativo | None = None
    estimado_gastos_mxn: DineroNoNegativo | None = None
    estimado_ingresos_usd: DineroNoNegativo | None = None
    estimado_gastos_usd: DineroNoNegativo | None = None
    trabajadores_estimados: int | None = Field(default=None, ge=0, le=1_000_000)
    fecha_inicio_estimada: date | None = None
    fecha_fin_estimada: date | None = None

    @model_validator(mode="after")
    def _fechas(self):
        if self.fecha_inicio_estimada and self.fecha_fin_estimada and self.fecha_fin_estimada < self.fecha_inicio_estimada:
            raise ValueError("La fecha estimada de terminación no puede ser anterior a la de inicio")
        return self


CAMPOS_PROYECCION = tuple(Proyeccion.model_fields)
CAMPOS_ESTIMADOS = ("estimado_ingresos_mxn", "estimado_gastos_mxn", "estimado_ingresos_usd", "estimado_gastos_usd")


class PartidaEstimadaCrear(BaseModel):
    """Ingreso o gasto estimado por categoría (opcional) y concepto (opcional)."""

    tipo: TipoEstimado
    categoria_id: uuid.UUID | None = None
    concepto: TextoOpcional = None
    moneda: Moneda
    monto: Dinero


class PartidaEstimadaActualizar(BaseModel):
    tipo: TipoEstimado | None = None
    categoria_id: uuid.UUID | None = None
    concepto: TextoOpcional = None
    moneda: Moneda | None = None
    monto: Dinero | None = None


class PartidaEstimadaOut(Registro):
    id: uuid.UUID
    proyecto_id: uuid.UUID
    tipo: TipoEstimado
    categoria_id: uuid.UUID | None
    categoria_nombre: str | None
    concepto: str | None
    moneda: Moneda
    monto: Decimal


class ProyectoCrear(Proyeccion):
    nombre: Nombre200
    descripcion: TextoOpcional = Field(default=None, max_length=2000)
    # Empresas a las que se vincula desde el inicio (opcional; también se vincula sola al capturar).
    empresa_ids: list[uuid.UUID] = []
    # Si se dan partidas, los totales estimados se calculan con ellas.
    partidas: list[PartidaEstimadaCrear] = Field(default=[], max_length=500)


class ProyectoActualizar(Proyeccion):
    nombre: Nombre200 | None = None
    descripcion: TextoOpcional = Field(default=None, max_length=2000)


class EmpresaBreve(ORMModel):
    id: uuid.UUID
    nombre: str
    activa: bool


class SaldoProyecto(BaseModel):
    moneda: Moneda
    ingresos: Decimal  # neto de las entradas
    gastos: Decimal  # porcentajes aplicados en las entradas
    salidas: Decimal
    saldo: Decimal


class SaldoProyectoEmpresa(SaldoProyecto):
    """Lo que el proyecto tiene en una empresa (negativo si usó dinero de otros proyectos)."""

    empresa_id: uuid.UUID
    empresa_nombre: str


class ProyectoOut(Registro):
    id: uuid.UUID
    nombre: str
    descripcion: str | None
    activo: bool
    empresas: list[EmpresaBreve]
    estimado_ingresos_mxn: Decimal | None
    estimado_gastos_mxn: Decimal | None
    estimado_ingresos_usd: Decimal | None
    estimado_gastos_usd: Decimal | None
    trabajadores_estimados: int | None
    fecha_inicio_estimada: date | None
    fecha_fin_estimada: date | None
    # Si es mayor que cero, los totales estimados son la suma de las partidas (no se capturan a mano).
    num_partidas_estimadas: int


class ProyectoResumen(ProyectoOut):
    saldos: list[SaldoProyecto]  # todas las empresas
    saldos_por_empresa: list[SaldoProyectoEmpresa]


class Vincular(BaseModel):
    empresa_id: uuid.UUID
