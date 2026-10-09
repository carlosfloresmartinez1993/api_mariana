from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import DB, UsuarioActual
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import DUMMY_HASH, create_access_token, hash_password, verify_password
from app.models import AccionBitacora, Usuario
from app.schemas.auth import CambioPassword, Token
from app.schemas.usuario import UsuarioOut
from app.services.bitacora import registrar

router = APIRouter(prefix="/auth", tags=["Autenticación"])

CREDENCIALES_INVALIDAS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Correo o contraseña incorrectos",
    headers={"WWW-Authenticate": "Bearer"},
)


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/login", response_model=Token)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
def login(request: Request, form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DB):
    """Login con correo (campo `username`) y contraseña. Devuelve un JWT de acceso."""
    usuario = db.scalar(select(Usuario).where(Usuario.correo == form.username.strip().lower()))
    if usuario is None:
        verify_password(form.password, DUMMY_HASH)  # mismo costo que un intento real
        raise CREDENCIALES_INVALIDAS
    if not verify_password(form.password, usuario.password_hash) or not usuario.activo:
        registrar(db, usuario_id=usuario.id, entidad="Usuario", entidad_id=usuario.id,
                  accion=AccionBitacora.INICIO_SESION_FALLIDO,
                  detalle={"ip": _ip(request), "motivo": "contraseña" if usuario.activo else "usuario inactivo"})
        db.commit()
        raise CREDENCIALES_INVALIDAS
    registrar(db, usuario_id=usuario.id, entidad="Usuario", entidad_id=usuario.id,
              accion=AccionBitacora.INICIO_SESION, detalle={"ip": _ip(request)})
    db.commit()
    token, expira_en = create_access_token(usuario.id)
    return Token(access_token=token, expires_in=expira_en)


@router.get("/me", response_model=UsuarioOut)
def yo(usuario: UsuarioActual):
    return usuario


@router.post("/cambiar-password", status_code=status.HTTP_204_NO_CONTENT)
def cambiar_password(datos: CambioPassword, usuario: UsuarioActual, db: DB):
    if not verify_password(datos.actual, usuario.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual no es correcta")
    usuario.password_hash = hash_password(datos.nueva)
    registrar(db, usuario_id=usuario.id, entidad="Usuario", entidad_id=usuario.id,
              accion=AccionBitacora.CAMBIO_PASSWORD, detalle={"por": "el propio usuario"})
    db.commit()
