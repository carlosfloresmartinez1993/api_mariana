"""Partidas estimadas (proyección por categoría) de un proyecto. No afectan saldos."""

import uuid

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app.api.deps import DB, UsuarioActual
from app.core.errors import ReglaNegocio
from app.models import AccionBitacora, Categoria, PartidaEstimada, Proyecto
from app.schemas.empresa import PartidaEstimadaActualizar, PartidaEstimadaCrear, PartidaEstimadaOut
from app.services import proyecciones
from app.services.acceso import obtener, verificar_autor
from app.services.bitacora import instantanea, registrar

router = APIRouter(tags=["Proyecciones"])


@router.get("/proyectos/{proyecto_id}/partidas-estimadas", response_model=list[PartidaEstimadaOut],
            summary="Ingresos y gastos estimados del proyecto")
def listar(proyecto_id: uuid.UUID, db: DB, _: UsuarioActual):
    obtener(db, Proyecto, proyecto_id, "Proyecto")
    return db.scalars(
        select(PartidaEstimada).outerjoin(PartidaEstimada.categoria)
        .where(PartidaEstimada.proyecto_id == proyecto_id)
        .order_by(PartidaEstimada.tipo.desc(), PartidaEstimada.moneda, Categoria.nombre.asc().nulls_last(),
                  PartidaEstimada.concepto, PartidaEstimada.fecha_creacion)).unique().all()


@router.post("/proyectos/{proyecto_id}/partidas-estimadas", response_model=PartidaEstimadaOut,
             status_code=status.HTTP_201_CREATED, summary="Agregar un ingreso o gasto estimado")
def crear(proyecto_id: uuid.UUID, datos: PartidaEstimadaCrear, db: DB, usuario: UsuarioActual):
    proyecto = obtener(db, Proyecto, proyecto_id, "Proyecto")
    partida = proyecciones.agregar(db, proyecto, datos, usuario)
    proyecciones.recalcular(db, proyecto)
    db.commit()
    db.refresh(partida)
    return partida


@router.patch("/partidas-estimadas/{partida_id}", response_model=PartidaEstimadaOut)
def actualizar(partida_id: uuid.UUID, datos: PartidaEstimadaActualizar, db: DB, usuario: UsuarioActual):
    partida = obtener(db, PartidaEstimada, partida_id, "Partida estimada")
    verificar_autor(usuario, partida)
    cambios = datos.model_dump(exclude_unset=True)
    if not cambios:
        raise ReglaNegocio("No se indicó ningún cambio")
    if nulos := sorted(c for c in ("tipo", "moneda", "monto") if c in cambios and cambios[c] is None):
        raise ReglaNegocio(f"Estos campos no pueden quedar vacíos: {', '.join(nulos)}")
    if cambios.get("categoria_id") and cambios["categoria_id"] != partida.categoria_id:
        proyecciones.categoria_activa(db, cambios["categoria_id"])
    antes = instantanea(partida, proyecciones.CAMPOS)
    for campo, valor in cambios.items():
        setattr(partida, campo, valor)
    proyecciones.recalcular(db, partida.proyecto)
    registrar(db, usuario_id=usuario.id, entidad="Partida estimada", entidad_id=partida.id,
              accion=AccionBitacora.EDITAR, detalle={"proyecto": partida.proyecto.nombre, "antes": antes,
                                                     "despues": instantanea(partida, proyecciones.CAMPOS)})
    db.commit()
    db.refresh(partida)
    return partida


@router.delete("/partidas-estimadas/{partida_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
               summary="Eliminar (no es dinero: se puede borrar; queda en la bitácora)")
def eliminar(partida_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    partida = obtener(db, PartidaEstimada, partida_id, "Partida estimada")
    verificar_autor(usuario, partida)
    proyecto = partida.proyecto
    registrar(db, usuario_id=usuario.id, entidad="Partida estimada", entidad_id=partida.id,
              accion=AccionBitacora.ELIMINAR, detalle={"proyecto": proyecto.nombre,
                                                       "antes": instantanea(partida, proyecciones.CAMPOS)})
    db.delete(partida)
    proyecciones.recalcular(db, proyecto)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
