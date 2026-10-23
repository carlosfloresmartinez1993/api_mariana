"""Partidas estimadas de la proyección de un proyecto (por categoría y concepto). No afectan saldos.

Si un proyecto tiene partidas, sus totales estimados de ingresos y gastos (MXN y USD) son la suma de ellas:
se recalculan en cada cambio y ya no se capturan a mano.
"""

import uuid
from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ReglaNegocio
from app.models import AccionBitacora, Categoria, Moneda, PartidaEstimada, Proyecto, TipoEstimado, Usuario
from app.schemas.empresa import CAMPOS_ESTIMADOS, PartidaEstimadaCrear
from app.services.acceso import obtener
from app.services.bitacora import instantanea, registrar

CAMPOS = ("proyecto_id", "tipo", "categoria_id", "concepto", "moneda", "monto")


def categoria_activa(db: Session, categoria_id: uuid.UUID | None) -> None:
    if categoria_id is None:
        return
    categoria = obtener(db, Categoria, categoria_id, "Categoría")
    if not categoria.activa:
        raise ReglaNegocio(f"La categoría «{categoria.nombre}» está desactivada")


def recalcular(db: Session, proyecto: Proyecto) -> dict[str, Any]:
    """Pone en el proyecto la suma de sus partidas. Si ya no tiene partidas, deja los totales como estaban."""
    db.flush()
    sumas: dict[str, Decimal] = defaultdict(Decimal)
    hay = False
    for tipo, moneda, total in db.execute(
            select(PartidaEstimada.tipo, PartidaEstimada.moneda, func.sum(PartidaEstimada.monto))
            .where(PartidaEstimada.proyecto_id == proyecto.id)
            .group_by(PartidaEstimada.tipo, PartidaEstimada.moneda)):
        hay = True
        clase = "ingresos" if TipoEstimado(tipo) == TipoEstimado.INGRESO else "gastos"
        sumas[f"estimado_{clase}_{Moneda(moneda).value.lower()}"] = Decimal(total)
    if hay:
        for campo in CAMPOS_ESTIMADOS:
            setattr(proyecto, campo, sumas.get(campo))
    db.flush()
    db.expire(proyecto, ["num_partidas_estimadas"])
    return instantanea(proyecto, CAMPOS_ESTIMADOS)


def agregar(db: Session, proyecto: Proyecto, datos: PartidaEstimadaCrear, usuario: Usuario) -> PartidaEstimada:
    """Sin commit: lo usa también el alta del proyecto."""
    categoria_activa(db, datos.categoria_id)
    partida = PartidaEstimada(**datos.model_dump(), proyecto_id=proyecto.id, creado_por=usuario.id)
    db.add(partida)
    db.flush()
    registrar(db, usuario_id=usuario.id, entidad="Partida estimada", entidad_id=partida.id,
              accion=AccionBitacora.CREAR, detalle={"proyecto": proyecto.nombre,
                                                    "despues": instantanea(partida, CAMPOS)})
    return partida


def validar_estimados_manuales(proyecto: Proyecto, cambios: dict[str, Any]) -> None:
    """Con partidas, los totales estimados no se editan a mano (sí se aceptan si no cambian)."""
    if not proyecto.num_partidas_estimadas:
        return
    distintos = [c for c in CAMPOS_ESTIMADOS if c in cambios and cambios[c] != getattr(proyecto, c)]
    if distintos:
        raise ReglaNegocio("Este proyecto tiene partidas estimadas: los totales estimados se calculan con ellas. "
                           "Edita las partidas en lugar de los totales.")
