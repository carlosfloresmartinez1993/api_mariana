from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Detrás de un proxy (nginx, etc.) arrancar uvicorn con --proxy-headers
# para que la IP del cliente sea la real y no la del proxy.
limiter = Limiter(key_func=get_remote_address, enabled=settings.RATE_LIMIT_ENABLED)
