import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import DB, UsuarioActual
from app.core.errors import Conflicto, ReglaNegocio
from app.models import AccionBitacora, Categoria
from app.schemas.categoria import CategoriaActualizar, CategoriaCrear, CategoriaOut
from app.services.acceso import obtener, verificar_autor
from app.services.bitacora import instantanea, registrar

router = APIRouter(prefix="/categorias", tags=["Categorías"])

CAMPOS = ("nombre", "descripcion", "activa")


def _nombre_libre(db: Session, nombre: str, excepto: uuid.UUID | None = None) -> None:
    stmt = select(Categoria.id).where(func.lower(Categoria.nombre) == nombre.lower())
    if excepto:
        stmt = stmt.where(Categoria.id != excepto)
    if db.scalar(stmt):
        raise Conflicto(f"Ya existe una categoría llamada «{nombre}»")


@router.get("", response_model=list[CategoriaOut], summary="Categorías de entradas y salidas")
def listar(db: DB, _: UsuarioActual, activa: Annotated[bool | None, Query()] = None):
    stmt = select(Categoria).order_by(Categoria.nombre)
    if activa is not None:
        stmt = stmt.where(Categoria.activa.is_(activa))
    return db.scalars(stmt).unique().all()


@router.post("", response_model=CategoriaOut, status_code=status.HTTP_201_CREATED)
def crear(datos: CategoriaCrear, db: DB, usuario: UsuarioActual):
    _nombre_libre(db, datos.nombre)
    categoria = Categoria(**datos.model_dump(), creado_por=usuario.id)
    db.add(categoria)
    db.flush()
    registrar(db, usuario_id=usuario.id, entidad="Categoría", entidad_id=categoria.id, accion=AccionBitacora.CREAR,
              detalle={"despues": instantanea(categoria, CAMPOS)})
    db.commit()
    return categoria


@router.patch("/{categoria_id}", response_model=CategoriaOut)
def actualizar(categoria_id: uuid.UUID, datos: CategoriaActualizar, db: DB, usuario: UsuarioActual):
    """Renombrar una categoría cambia el nombre en todos los movimientos que la usan."""
    categoria = obtener(db, Categoria, categoria_id, "Categoría")
    verificar_autor(usuario, categoria)
    cambios = datos.model_dump(exclude_unset=True)
    if not cambios:
        raise ReglaNegocio("No se indicó ningún cambio")
    if "nombre" in cambios:
        if cambios["nombre"] is None:
            raise ReglaNegocio("El nombre no puede quedar vacío")
        _nombre_libre(db, cambios["nombre"], excepto=categoria.id)
    antes = instantanea(categoria, CAMPOS)
    for campo, valor in cambios.items():
        setattr(categoria, campo, valor)
    registrar(db, usuario_id=usuario.id, entidad="Categoría", entidad_id=categoria.id, accion=AccionBitacora.EDITAR,
              detalle={"antes": antes, "despues": instantanea(categoria, CAMPOS)})
    db.commit()
    return categoria


def _cambiar_estado(db: Session, categoria_id: uuid.UUID, usuario, activa: bool) -> Categoria:
    categoria = obtener(db, Categoria, categoria_id, "Categoría")
    verificar_autor(usuario, categoria)
    if categoria.activa != activa:
        categoria.activa = activa
        registrar(db, usuario_id=usuario.id, entidad="Categoría", entidad_id=categoria.id,
                  accion=AccionBitacora.ACTIVAR if activa else AccionBitacora.DESACTIVAR,
                  detalle={"nombre": categoria.nombre})
        db.commit()
    return categoria


@router.post("/{categoria_id}/activar", response_model=CategoriaOut)
def activar(categoria_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    return _cambiar_estado(db, categoria_id, usuario, True)


@router.post("/{categoria_id}/desactivar", response_model=CategoriaOut)
def desactivar(categoria_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    """Ya no se ofrece al capturar. Los movimientos que la tienen la conservan."""
    return _cambiar_estado(db, categoria_id, usuario, False)
