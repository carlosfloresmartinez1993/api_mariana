import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import IntegrityError

from app.api.routes import auth, bitacora, cuentas, empresas, movimientos, proyectos, reportes, usuarios
from app.core.config import settings
from app.core.errors import ErrorDominio
from app.core.rate_limit import limiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app")


def _asegurar_superusuario() -> None:
    """Crea (o restablece) el superusuario con SUPERUSUARIO_* en cada arranque, sea cual sea el servidor."""
    if not settings.SUPERUSUARIO_CORREO or not settings.SUPERUSUARIO_PASSWORD:
        logger.warning("SUPERUSUARIO_CORREO / SUPERUSUARIO_PASSWORD no definidas: no se verifica el superusuario")
        return
    from app.db.session import SessionLocal
    from app.services.usuarios import asegurar_superusuario

    try:
        with SessionLocal() as db:
            mensaje = asegurar_superusuario(
                db,
                correo=settings.SUPERUSUARIO_CORREO,
                password=settings.SUPERUSUARIO_PASSWORD.get_secret_value(),
                nombre=settings.SUPERUSUARIO_NOMBRE,
                restablecer=settings.SUPERUSUARIO_RESTABLECER,
            )
        logger.info(mensaje)
    except Exception:  # noqa: BLE001 — la API debe arrancar aunque esto falle (p. ej. sin migraciones)
        logger.exception("No se pudo verificar el superusuario")


@asynccontextmanager
async def lifespan(_: FastAPI):
    _asegurar_superusuario()
    yield


docs = settings.DOCS_ENABLED
app = FastAPI(
    title=settings.APP_NAME,
    description="Entradas, salidas y saldos por empresa, cuenta y proyecto.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if docs else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=False,  # se usa token Bearer, no cookies
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )


@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):
    respuesta = await call_next(request)
    respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
    respuesta.headers.setdefault("X-Frame-Options", "DENY")
    respuesta.headers.setdefault("Referrer-Policy", "no-referrer")
    if not request.url.path.startswith(("/docs", "/openapi.json")):
        respuesta.headers.setdefault("Cache-Control", "no-store")
    if settings.ENVIRONMENT == "production":
        respuesta.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return respuesta


@app.exception_handler(ErrorDominio)
async def manejar_error_dominio(_: Request, exc: ErrorDominio):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detalle})


@app.exception_handler(IntegrityError)
async def manejar_integridad(_: Request, exc: IntegrityError):
    # Respaldo ante carreras (p. ej. dos altas simultáneas con el mismo correo).
    logger.warning("Violación de integridad: %s", exc.orig)
    return JSONResponse(status_code=409, content={"detail": "La operación entra en conflicto con datos existentes"})


@app.exception_handler(Exception)
async def manejar_error_inesperado(_: Request, exc: Exception):
    logger.exception("Error no controlado", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


for router in (auth.router, usuarios.router, empresas.router, cuentas.router, proyectos.router, movimientos.entradas,
               movimientos.salidas, reportes.router, bitacora.router):
    app.include_router(router)


@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok"}
