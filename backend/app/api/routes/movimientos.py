import uuid
from datetime import date
from enum import StrEnum

from fastapi import APIRouter, File, Response, UploadFile, status
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
from app.services import facturas
from app.services import movimientos as svc
from app.services.acceso import obtener


class Estado(StrEnum):
    VIGENTES = "vigentes"
    ANULADOS = "anulados"
    TODOS = "todos"


class FiltroFactura(StrEnum):
    REQUERIDA = "requerida"  # tiene marcada la casilla
    PENDIENTE = "pendiente"  # la requiere y aún no tiene archivo
    ADJUNTA = "adjunta"  # tiene archivo
    SIN = "sin"  # no la requiere ni tiene archivo


def _comunes(stmt: Select, modelo, estado: Estado, desde: date | None, hasta: date | None,
             moneda: Moneda | None, factura: FiltroFactura | None = None) -> Select:
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
    if factura == FiltroFactura.REQUERIDA:
        stmt = stmt.where(modelo.requiere_factura.is_(True))
    elif factura == FiltroFactura.PENDIENTE:
        stmt = stmt.where(modelo.requiere_factura.is_(True), modelo.factura_clave.is_(None))
    elif factura == FiltroFactura.ADJUNTA:
        stmt = stmt.where(modelo.factura_clave.is_not(None))
    elif factura == FiltroFactura.SIN:
        stmt = stmt.where(modelo.requiere_factura.is_(False), modelo.factura_clave.is_(None))
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
                    hasta: date | None = None, estado: Estado = Estado.VIGENTES, q: str | None = None,
                    factura: FiltroFactura | None = None, categoria_id: uuid.UUID | None = None):
    stmt = _comunes(select(Entrada), Entrada, estado, desde, hasta, moneda, factura)
    for columna, valor in ((Entrada.proyecto_id, proyecto_id), (Entrada.empresa_id, empresa_id), (Entrada.categoria_id, categoria_id),
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
                   hasta: date | None = None, estado: Estado = Estado.VIGENTES, q: str | None = None,
                   factura: FiltroFactura | None = None, categoria_id: uuid.UUID | None = None):
    stmt = _comunes(select(Salida), Salida, estado, desde, hasta, moneda, factura)
    for columna, valor in ((Salida.proyecto_id, proyecto_id), (Salida.empresa_id, empresa_id), (Salida.categoria_id, categoria_id),
                           (Salida.cuenta_id, cuenta_id), (Salida.forma, forma)):
        if valor:
            stmt = stmt.where(columna == valor)
    stmt = _texto(stmt, q, Salida.concepto, Salida.beneficiario)
    return paginar(db, stmt, pag.limit, pag.offset)


@salidas.post("", response_model=SalidaOut, status_code=status.HTTP_201_CREATED)
def crear_salida(datos: SalidaCrear, db: DB, usuario: UsuarioActual):
    """Debe alcanzar el saldo de la cuenta. El proyecto sí puede quedar en negativo."""
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


# ------------------------------------------------------------------ factura (opcional)
def _rutas_factura(router: APIRouter, modelo, nombre: str, esquema) -> None:
    """PUT / GET / DELETE /{id}/factura para entradas y salidas."""

    @router.put("/{mov_id}/factura", response_model=esquema, summary=f"Adjuntar factura a la {nombre.lower()}")
    async def subir(mov_id: uuid.UUID, db: DB, usuario: UsuarioActual, archivo: UploadFile = File(...)):
        """PDF, XML, JPG o PNG. Si ya tenía una, la reemplaza."""
        return await facturas.subir(db, obtener(db, modelo, mov_id, nombre), archivo, usuario)

    @router.get("/{mov_id}/factura", response_class=Response, summary="Ver o descargar la factura")
    def descargar(mov_id: uuid.UUID, db: DB, _: UsuarioActual):
        datos, tipo, encabezados = facturas.contenido(obtener(db, modelo, mov_id, nombre))
        return Response(datos, media_type=tipo, headers=encabezados)

    @router.delete("/{mov_id}/factura", response_model=esquema, summary="Quitar la factura")
    def quitar(mov_id: uuid.UUID, db: DB, usuario: UsuarioActual):
        return facturas.quitar(db, obtener(db, modelo, mov_id, nombre), usuario)


_rutas_factura(entradas, Entrada, "Entrada", EntradaOut)
_rutas_factura(salidas, Salida, "Salida", SalidaOut)
