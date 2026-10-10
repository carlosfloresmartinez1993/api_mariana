import uuid
from datetime import date
from enum import StrEnum

from fastapi import APIRouter, status
from sqlalchemy import Select, or_, select

from app.api.deps import DB, PaginacionDep, UsuarioActual
from app.api.utils import paginar
from app.core.errors import ReglaNegocio
from app.models import Entrada, Forma, Moneda, Salida
from app.schemas.comun import ConMotivo, Pagina
from app.schemas.movimiento import (
    EntradaActualizar,
    EntradaCrear,
    EntradaOut,
    SalidaActualizar,
    SalidaCrear,
    SalidaOut,
)
from app.services import movimientos as svc
from app.services.acceso import obtener


class Estado(StrEnum):
    VIGENTES = "vigentes"
    ANULADOS = "anulados"
    TODOS = "todos"


def _comunes(stmt: Select, modelo, estado: Estado, desde: date | None, hasta: date | None,
             moneda: Moneda | None) -> Select:
    if desde and hasta and desde > hasta:
        raise ReglaNegocio("La fecha inicial no puede ser posterior a la final")
    if estado != Estado.TODOS:
        stmt = stmt.where(modelo.anulado.is_(estado == Estado.ANULADOS))
    if desde:
        stmt = stmt.where(modelo.fecha >= desde)
    if hasta:
        stmt = stmt.where(modelo.fecha <= hasta)
    if moneda:
        stmt = stmt.where(modelo.moneda == moneda)
    return stmt.order_by(modelo.fecha.desc(), modelo.fecha_creacion.desc())


def _texto(stmt: Select, q: str | None, *columnas) -> Select:
    if q and q.strip():
        patron = f"%{q.strip()}%"
        stmt = stmt.where(or_(*(c.ilike(patron) for c in columnas)))
    return stmt


# ------------------------------------------------------------------ entradas
entradas = APIRouter(prefix="/entradas", tags=["Entradas"])


@entradas.get("", response_model=Pagina[EntradaOut])
def listar_entradas(db: DB, _: UsuarioActual, pag: PaginacionDep, proyecto_id: uuid.UUID | None = None,
                    empresa_id: uuid.UUID | None = None, cuenta_id: uuid.UUID | None = None,
                    moneda: Moneda | None = None, forma: Forma | None = None, desde: date | None = None,
                    hasta: date | None = None, estado: Estado = Estado.VIGENTES, q: str | None = None):
    stmt = _comunes(select(Entrada), Entrada, estado, desde, hasta, moneda)
    for columna, valor in ((Entrada.proyecto_id, proyecto_id), (Entrada.empresa_id, empresa_id),
                           (Entrada.cuenta_id, cuenta_id), (Entrada.forma, forma)):
        if valor:
            stmt = stmt.where(columna == valor)
    stmt = _texto(stmt, q, Entrada.concepto, Entrada.referencia)
    return paginar(db, stmt, pag.limit, pag.offset)


@entradas.post("", response_model=EntradaOut, status_code=status.HTTP_201_CREATED)
def crear_entrada(datos: EntradaCrear, db: DB, usuario: UsuarioActual):
    """El porcentaje (opcional) es gasto del proyecto: a la cuenta llega el neto."""
    return svc.crear_entrada(db, datos, usuario)


@entradas.get("/{entrada_id}", response_model=EntradaOut)
def obtener_entrada(entrada_id: uuid.UUID, db: DB, _: UsuarioActual):
    return obtener(db, Entrada, entrada_id, "Entrada")


@entradas.patch("/{entrada_id}", response_model=EntradaOut)
def editar_entrada(entrada_id: uuid.UUID, datos: EntradaActualizar, db: DB, usuario: UsuarioActual):
    return svc.editar(db, obtener(db, Entrada, entrada_id, "Entrada"), datos.model_dump(exclude_unset=True), usuario)


@entradas.post("/{entrada_id}/anular", response_model=EntradaOut)
def anular_entrada(entrada_id: uuid.UUID, datos: ConMotivo, db: DB, usuario: UsuarioActual):
    return svc.anular(db, obtener(db, Entrada, entrada_id, "Entrada"), datos.motivo, usuario)


# ------------------------------------------------------------------ salidas
salidas = APIRouter(prefix="/salidas", tags=["Salidas"])


@salidas.get("", response_model=Pagina[SalidaOut])
def listar_salidas(db: DB, _: UsuarioActual, pag: PaginacionDep, proyecto_id: uuid.UUID | None = None,
                   empresa_id: uuid.UUID | None = None, cuenta_id: uuid.UUID | None = None,
                   moneda: Moneda | None = None, forma: Forma | None = None, desde: date | None = None,
                   hasta: date | None = None, estado: Estado = Estado.VIGENTES, q: str | None = None):
    stmt = _comunes(select(Salida), Salida, estado, desde, hasta, moneda)
    for columna, valor in ((Salida.proyecto_id, proyecto_id), (Salida.empresa_id, empresa_id),
                           (Salida.cuenta_id, cuenta_id), (Salida.forma, forma)):
        if valor:
            stmt = stmt.where(columna == valor)
    stmt = _texto(stmt, q, Salida.concepto, Salida.beneficiario)
    return paginar(db, stmt, pag.limit, pag.offset)


@salidas.post("", response_model=SalidaOut, status_code=status.HTTP_201_CREATED)
def crear_salida(datos: SalidaCrear, db: DB, usuario: UsuarioActual):
    """Debe alcanzar el saldo del proyecto en esa moneda y el de la cuenta."""
    return svc.crear_salida(db, datos, usuario)


@salidas.get("/{salida_id}", response_model=SalidaOut)
def obtener_salida(salida_id: uuid.UUID, db: DB, _: UsuarioActual):
    return obtener(db, Salida, salida_id, "Salida")


@salidas.patch("/{salida_id}", response_model=SalidaOut)
def editar_salida(salida_id: uuid.UUID, datos: SalidaActualizar, db: DB, usuario: UsuarioActual):
    return svc.editar(db, obtener(db, Salida, salida_id, "Salida"), datos.model_dump(exclude_unset=True), usuario)


@salidas.post("/{salida_id}/anular", response_model=SalidaOut)
def anular_salida(salida_id: uuid.UUID, datos: ConMotivo, db: DB, usuario: UsuarioActual):
    return svc.anular(db, obtener(db, Salida, salida_id, "Salida"), datos.motivo, usuario)

