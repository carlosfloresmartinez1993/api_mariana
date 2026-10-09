import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import DB, Admin, PaginacionDep, UsuarioActual
from app.api.utils import cambios_no_nulos, paginar
from app.core.errors import NoEncontrado, ReglaNegocio
from app.core.security import hash_password
from app.models import AccionBitacora, Rol, Usuario
from app.schemas.comun import Pagina
from app.schemas.usuario import RestablecerPassword, UsuarioActualizar, UsuarioCrear, UsuarioOut
from app.services.bitacora import instantanea, registrar
from app.services.usuarios import correo_libre, verificar_puede_administrar

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])

CAMPOS = ("nombre", "correo", "rol", "activo")


def _obtener(db: Session, usuario_id: uuid.UUID) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise NoEncontrado("Usuario no encontrado")
    return usuario


@router.get("/catalogo", response_model=list[UsuarioOut], summary="Todos los usuarios (para filtros y «registrado por»)")
def catalogo(db: DB, _: UsuarioActual):
    return db.scalars(select(Usuario).order_by(Usuario.nombre)).all()


@router.get("", response_model=Pagina[UsuarioOut])
def listar(db: DB, _: Admin, pag: PaginacionDep, rol: Rol | None = None,
           activo: Annotated[bool | None, Query()] = None):
    stmt = select(Usuario).order_by(Usuario.nombre)
    if rol:
        stmt = stmt.where(Usuario.rol == rol)
    if activo is not None:
        stmt = stmt.where(Usuario.activo.is_(activo))
    return paginar(db, stmt, pag.limit, pag.offset)


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear(datos: UsuarioCrear, db: DB, actor: Admin):
    """El superusuario crea administradores y contadores; un administrador, solo contadores."""
    verificar_puede_administrar(actor, datos.rol)
    correo_libre(db, datos.correo)
    usuario = Usuario(**datos.model_dump(exclude={"password"}), password_hash=hash_password(datos.password))
    db.add(usuario)
    db.flush()
    registrar(db, usuario_id=actor.id, entidad="Usuario", entidad_id=usuario.id,
              accion=AccionBitacora.CREAR, detalle={"despues": instantanea(usuario, CAMPOS)})
    db.commit()
    return usuario


@router.get("/{usuario_id}", response_model=UsuarioOut)
def obtener(usuario_id: uuid.UUID, db: DB, _: Admin):
    return _obtener(db, usuario_id)


@router.patch("/{usuario_id}", response_model=UsuarioOut)
def actualizar(usuario_id: uuid.UUID, datos: UsuarioActualizar, db: DB, actor: Admin):
    usuario = _obtener(db, usuario_id)
    verificar_puede_administrar(actor, usuario.rol)
    cambios = cambios_no_nulos(datos.model_dump(exclude_unset=True), {"nombre", "correo", "rol"})
    if "rol" in cambios:
        verificar_puede_administrar(actor, cambios["rol"])
    if "correo" in cambios:
        correo_libre(db, cambios["correo"], excepto=usuario.id)
    antes = instantanea(usuario, CAMPOS)
    for campo, valor in cambios.items():
        setattr(usuario, campo, valor)
    registrar(db, usuario_id=actor.id, entidad="Usuario", entidad_id=usuario.id,
              accion=AccionBitacora.EDITAR, detalle={"antes": antes, "despues": instantanea(usuario, CAMPOS)})
    db.commit()
    return usuario


@router.post("/{usuario_id}/activar", response_model=UsuarioOut)
def activar(usuario_id: uuid.UUID, db: DB, actor: Admin):
    usuario = _obtener(db, usuario_id)
    verificar_puede_administrar(actor, usuario.rol)
    if not usuario.activo:
        usuario.activo = True
        registrar(db, usuario_id=actor.id, entidad="Usuario", entidad_id=usuario.id, accion=AccionBitacora.ACTIVAR)
        db.commit()
    return usuario


@router.post("/{usuario_id}/desactivar", response_model=UsuarioOut)
def desactivar(usuario_id: uuid.UUID, db: DB, actor: Admin):
    """El usuario pierde el acceso de inmediato. Lo que registró se conserva."""
    usuario = _obtener(db, usuario_id)
    if usuario.id == actor.id:
        raise ReglaNegocio("No puedes desactivar tu propia cuenta")
    verificar_puede_administrar(actor, usuario.rol)
    if usuario.activo:
        usuario.activo = False
        registrar(db, usuario_id=actor.id, entidad="Usuario", entidad_id=usuario.id, accion=AccionBitacora.DESACTIVAR)
        db.commit()
    return usuario


@router.post("/{usuario_id}/restablecer-password", status_code=status.HTTP_204_NO_CONTENT)
def restablecer_password(usuario_id: uuid.UUID, datos: RestablecerPassword, db: DB, actor: Admin):
    usuario = _obtener(db, usuario_id)
    verificar_puede_administrar(actor, usuario.rol)
    usuario.password_hash = hash_password(datos.nueva)
    registrar(db, usuario_id=actor.id, entidad="Usuario", entidad_id=usuario.id,
              accion=AccionBitacora.CAMBIO_PASSWORD, detalle={"por": actor.rol})
    db.commit()
