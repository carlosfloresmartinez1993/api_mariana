import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DB, Admin, PaginacionDep
from app.api.utils import paginar
from app.core.config import settings
from app.core.errors import ReglaNegocio
from app.models import AccionBitacora, Bitacora
from app.schemas.bitacora import BitacoraOut
from app.schemas.comun import Pagina

router = APIRouter(prefix="/bitacora", tags=["Bitácora"])


def _inicio_del_dia(dia: date) -> datetime:
    return datetime.combine(dia, time.min, ZoneInfo(settings.TIMEZONE))


@router.get("", response_model=Pagina[BitacoraOut], summary="Qué hizo cada usuario (admin)")
def listar(db: DB, _: Admin, pag: PaginacionDep, usuario_id: uuid.UUID | None = None, entidad: str | None = None,
           entidad_id: uuid.UUID | None = None, accion: AccionBitacora | None = None,
           desde: date | None = None, hasta: date | None = None):
    """Más recientes primero. `desde` y `hasta` son días completos en la zona horaria del negocio."""
    if desde and hasta and desde > hasta:
        raise ReglaNegocio("La fecha inicial no puede ser posterior a la final")
    stmt = select(Bitacora).order_by(Bitacora.fecha.desc(), Bitacora.id)
    if usuario_id:
        stmt = stmt.where(Bitacora.usuario_id == usuario_id)
    if entidad:
        stmt = stmt.where(Bitacora.entidad == entidad)
    if entidad_id:
        stmt = stmt.where(Bitacora.entidad_id == entidad_id)
    if accion:
        stmt = stmt.where(Bitacora.accion == accion)
    if desde:
        stmt = stmt.where(Bitacora.fecha >= _inicio_del_dia(desde))
    if hasta:
        stmt = stmt.where(Bitacora.fecha < _inicio_del_dia(hasta + timedelta(days=1)))
    return paginar(db, stmt, pag.limit, pag.offset)
