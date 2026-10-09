import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

DB = Annotated[Session, Depends(get_db)]


def get_current_user(db: DB, token: Annotated[str, Depends(oauth2_scheme)]) -> Usuario:
    error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o sesión expirada",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        usuario_id = uuid.UUID(decode_access_token(token)["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise error from None
    # Se consulta en cada petición para que desactivar a un usuario corte su acceso de inmediato.
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        raise error
    return usuario


UsuarioActual = Annotated[Usuario, Depends(get_current_user)]


def require_admin(usuario: UsuarioActual) -> Usuario:
    """Administrador o superusuario."""
    if not usuario.es_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere rol de administrador")
    return usuario


Admin = Annotated[Usuario, Depends(require_admin)]


class Paginacion:
    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ):
        self.limit = limit
        self.offset = offset


PaginacionDep = Annotated[Paginacion, Depends()]
