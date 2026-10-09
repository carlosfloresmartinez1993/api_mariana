import uuid
from datetime import timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import settings
from app.core.tiempo import ahora

BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# Hash de relleno: al intentar login con un correo inexistente se verifica contra
# este hash para que el tiempo de respuesta no revele qué correos existen.
DUMMY_HASH = hash_password(uuid.uuid4().hex)


def create_access_token(usuario_id: uuid.UUID) -> tuple[str, int]:
    """Devuelve (token, segundos de vigencia)."""
    expira_en = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    momento = ahora()
    payload: dict[str, Any] = {
        "sub": str(usuario_id),
        "type": "access",
        "iat": momento,
        "exp": momento + timedelta(seconds=expira_en),
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expira_en


def decode_access_token(token: str) -> dict[str, Any]:
    """Lanza jwt.PyJWTError si el token es inválido, expiró o no es de acceso."""
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["sub", "exp", "iat", "type"]},
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Tipo de token inválido")
    return payload
