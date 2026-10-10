import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import Moneda, TipoCuenta
from app.schemas.comun import Nombre100, Nombre200, ORMModel, TextoOpcional


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
class ProyectoCrear(BaseModel):
    nombre: Nombre200
    descripcion: TextoOpcional = Field(default=None, max_length=2000)
    # Empresas a las que se vincula desde el inicio (opcional; también se vincula sola al capturar).
    empresa_ids: list[uuid.UUID] = []


class ProyectoActualizar(BaseModel):
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
    """Lo que el proyecto tiene en una empresa: solo de ahí puede salir ese dinero."""

    empresa_id: uuid.UUID
    empresa_nombre: str


class ProyectoOut(Registro):
    id: uuid.UUID
    nombre: str
    descripcion: str | None
    activo: bool
    empresas: list[EmpresaBreve]


class ProyectoResumen(ProyectoOut):
    saldos: list[SaldoProyecto]  # todas las empresas
    saldos_por_empresa: list[SaldoProyectoEmpresa]


class Vincular(BaseModel):
    empresa_id: uuid.UUID
