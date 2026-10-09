from datetime import date
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.errors import ReglaNegocio
from app.core.tiempo import hoy


def paginar(db: Session, stmt: Select, limit: int, offset: int) -> dict[str, Any]:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    items = list(db.scalars(stmt.limit(limit).offset(offset)).unique())
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def cambios_no_nulos(datos: dict[str, Any], obligatorios: set[str]) -> dict[str, Any]:
    """Valida un PATCH: debe traer algo y no puede anular campos obligatorios."""
    if not datos:
        raise ReglaNegocio("No se indicó ningún cambio")
    nulos = [c for c in obligatorios if c in datos and datos[c] is None]
    if nulos:
        raise ReglaNegocio(f"Estos campos no pueden ser nulos: {', '.join(sorted(nulos))}")
    return datos


def validar_no_futura(fecha: date, campo: str = "fecha") -> None:
    if fecha > hoy():
        raise ReglaNegocio(f"La {campo} no puede ser futura")
