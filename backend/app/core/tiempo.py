from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import settings


def ahora() -> datetime:
    return datetime.now(ZoneInfo(settings.TIMEZONE))


def hoy() -> date:
    """Fecha actual en la zona horaria del negocio (no la del servidor)."""
    return ahora().date()
