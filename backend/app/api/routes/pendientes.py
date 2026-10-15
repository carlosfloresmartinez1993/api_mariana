"""Cuentas por cobrar y por pagar de los proyectos. No afectan saldos."""

import uuid
from enum import StrEnum

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app.api.deps import DB, UsuarioActual
from app.core.errors import ReglaNegocio
from app.core.tiempo import hoy
from app.models import AccionBitacora, Moneda, Pendiente, Proyecto, TipoPendiente
from app.schemas.pendiente import PendienteActualizar, PendienteCrear, PendienteOut
from app.services.acceso import obtener, verificar_autor
from app.services.bitacora import instantanea, registrar

router = APIRouter(tags=["Cuentas por cobrar y por pagar"])

CAMPOS = ("proyecto_id", "tipo", "concepto", "contraparte", "moneda", "monto", "fecha_vencimiento", "liquidada",
          "fecha_liquidacion", "nota")


class EstadoPendiente(StrEnum):
    PENDIENTES = "pendientes"
    LIQUIDADAS = "liquidadas"
    VENCIDAS = "vencidas"
    TODAS = "todas"


def salida(p: Pendiente) -> PendienteOut:
    vencida = not p.liquidada and p.fecha_vencimiento is not None and p.fecha_vencimiento < hoy()
    campos = {c: getattr(p, c) for c in PendienteOut.model_fields if c != "vencida"}
    return PendienteOut(**campos, vencida=vencida)


@router.get("/pendientes", response_model=list[PendienteOut], summary="Todas las cuentas por cobrar y por pagar")
def listar(db: DB, _: UsuarioActual, proyecto_id: uuid.UUID | None = None, tipo: TipoPendiente | None = None,
           moneda: Moneda | None = None, estado: EstadoPendiente = EstadoPendiente.PENDIENTES):
    stmt = select(Pendiente).join(Pendiente.proyecto).order_by(
        Pendiente.liquidada, Pendiente.fecha_vencimiento.asc().nulls_last(), Proyecto.nombre, Pendiente.concepto)
    if proyecto_id:
        stmt = stmt.where(Pendiente.proyecto_id == proyecto_id)
    if tipo:
        stmt = stmt.where(Pendiente.tipo == tipo)
    if moneda:
        stmt = stmt.where(Pendiente.moneda == moneda)
    if estado == EstadoPendiente.PENDIENTES:
        stmt = stmt.where(Pendiente.liquidada.is_(False))
    elif estado == EstadoPendiente.LIQUIDADAS:
        stmt = stmt.where(Pendiente.liquidada.is_(True))
    elif estado == EstadoPendiente.VENCIDAS:
        stmt = stmt.where(Pendiente.liquidada.is_(False), Pendiente.fecha_vencimiento < hoy())
    return [salida(p) for p in db.scalars(stmt).unique()]


@router.post("/proyectos/{proyecto_id}/pendientes", response_model=PendienteOut, status_code=status.HTTP_201_CREATED,
             summary="Agregar una cuenta por cobrar o por pagar al proyecto")
def crear(proyecto_id: uuid.UUID, datos: PendienteCrear, db: DB, usuario: UsuarioActual):
    proyecto = obtener(db, Proyecto, proyecto_id, "Proyecto")
    pendiente = Pendiente(**datos.model_dump(), proyecto_id=proyecto.id, creado_por=usuario.id)
    db.add(pendiente)
    db.flush()
    registrar(db, usuario_id=usuario.id, entidad="Pendiente", entidad_id=pendiente.id, accion=AccionBitacora.CREAR,
              detalle={"proyecto": proyecto.nombre, "despues": instantanea(pendiente, CAMPOS)})
    db.commit()
    db.refresh(pendiente)
    return salida(pendiente)


@router.patch("/pendientes/{pendiente_id}", response_model=PendienteOut, summary="Editar o liquidar")
def actualizar(pendiente_id: uuid.UUID, datos: PendienteActualizar, db: DB, usuario: UsuarioActual):
    pendiente = obtener(db, Pendiente, pendiente_id, "Partida")
    verificar_autor(usuario, pendiente)
    cambios = datos.model_dump(exclude_unset=True)
    if not cambios:
        raise ReglaNegocio("No se indicó ningún cambio")
    if nulos := sorted(c for c in ("tipo", "concepto", "moneda", "monto", "liquidada") if c in cambios
                       and cambios[c] is None):
        raise ReglaNegocio(f"Estos campos no pueden quedar vacíos: {', '.join(nulos)}")
    antes = instantanea(pendiente, CAMPOS)
    liquida = cambios.get("liquidada") is True and not pendiente.liquidada
    for campo, valor in cambios.items():
        setattr(pendiente, campo, valor)
    if pendiente.liquidada and pendiente.fecha_liquidacion is None:
        pendiente.fecha_liquidacion = hoy()
    if not pendiente.liquidada:
        pendiente.fecha_liquidacion = None
    registrar(db, usuario_id=usuario.id, entidad="Pendiente", entidad_id=pendiente.id,
              accion=AccionBitacora.LIQUIDAR if liquida else AccionBitacora.EDITAR,
              detalle={"antes": antes, "despues": instantanea(pendiente, CAMPOS)})
    db.commit()
    db.refresh(pendiente)
    return salida(pendiente)


@router.delete("/pendientes/{pendiente_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
               summary="Eliminar (no es dinero: se puede borrar; queda en la bitácora)")
def eliminar(pendiente_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    pendiente = obtener(db, Pendiente, pendiente_id, "Partida")
    verificar_autor(usuario, pendiente)
    registrar(db, usuario_id=usuario.id, entidad="Pendiente", entidad_id=pendiente.id, accion=AccionBitacora.ELIMINAR,
              detalle={"antes": instantanea(pendiente, CAMPOS)})
    db.delete(pendiente)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
