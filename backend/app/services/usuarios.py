"""Reglas sobre usuarios y roles.

- superusuario: único; se crea desde las variables de entorno. Administra admins y contadores.
  Nadie lo puede editar, desactivar ni cambiar de rol por la API (solo él cambia su contraseña).
- admin: administra contadores.
- contador: no administra usuarios.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflicto, Prohibido, ReglaNegocio
from app.core.security import hash_password
from app.models import AccionBitacora, Rol, Usuario
from app.schemas.comun import validar_password
from app.services.bitacora import registrar


def roles_que_administra(actor: Usuario) -> set[Rol]:
    if actor.es_superusuario:
        return {Rol.ADMIN, Rol.CONTADOR}
    if actor.rol == Rol.ADMIN:
        return {Rol.CONTADOR}
    return set()


def verificar_puede_administrar(actor: Usuario, rol_objetivo: Rol) -> None:
    if rol_objetivo not in roles_que_administra(actor):
        if rol_objetivo == Rol.SUPERUSUARIO:
            raise Prohibido("El superusuario solo se administra desde las variables de entorno")
        raise Prohibido("Solo el superusuario puede administrar a los administradores")


def correo_libre(db: Session, correo: str, excepto: uuid.UUID | None = None) -> None:
    stmt = select(Usuario.id).where(Usuario.correo == correo)
    if excepto:
        stmt = stmt.where(Usuario.id != excepto)
    if db.scalar(stmt):
        raise Conflicto("Ya existe un usuario con ese correo")


def asegurar_superusuario(db: Session, *, correo: str, password: str, nombre: str, restablecer: bool) -> str:
    """Crea el superusuario si no existe; con `restablecer`, le vuelve a asignar la contraseña.

    Es idempotente: se puede ejecutar en cada arranque. Devuelve un mensaje de lo que hizo.
    """
    correo = correo.strip().lower()
    try:
        validar_password(password)
    except ValueError as exc:
        raise ReglaNegocio(f"SUPERUSUARIO_PASSWORD inválida: {exc}") from None

    existente = db.scalar(select(Usuario).where(Usuario.rol == Rol.SUPERUSUARIO))
    if existente is None:
        correo_libre(db, correo)
        su = Usuario(nombre=nombre, correo=correo, password_hash=hash_password(password), rol=Rol.SUPERUSUARIO)
        db.add(su)
        db.flush()
        registrar(db, usuario_id=None, entidad="Usuario", entidad_id=su.id, accion=AccionBitacora.CREAR,
                  detalle={"correo": correo, "rol": Rol.SUPERUSUARIO, "origen": "variables de entorno"})
        db.commit()
        return f"superusuario creado: {correo}"

    if not restablecer:
        return "el superusuario ya existe"

    if existente.correo != correo:
        correo_libre(db, correo, excepto=existente.id)
    antes = existente.correo
    existente.correo = correo
    existente.password_hash = hash_password(password)
    existente.activo = True
    registrar(db, usuario_id=None, entidad="Usuario", entidad_id=existente.id, accion=AccionBitacora.CAMBIO_PASSWORD,
              detalle={"por": "SUPERUSUARIO_RESTABLECER", "correo_antes": antes, "correo": correo})
    db.commit()
    return f"superusuario restablecido: {correo}"
