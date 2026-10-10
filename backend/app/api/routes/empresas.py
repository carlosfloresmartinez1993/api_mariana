import uuid
from collections import defaultdict
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import DB, PaginacionDep, UsuarioActual
from app.api.utils import paginar
from app.core.errors import Conflicto
from app.models import AccionBitacora, Cuenta, Empresa, EmpresaProyecto
from app.schemas.comun import Pagina
from app.schemas.empresa import EmpresaActualizar, EmpresaCrear, EmpresaOut, EmpresaResumen
from app.services.acceso import obtener, verificar_autor
from app.services.bitacora import registrar
from app.services.saldos import saldos_cuentas

router = APIRouter(prefix="/empresas", tags=["Empresas"])


def _nombre_libre(db: Session, nombre: str, excepto: uuid.UUID | None = None) -> None:
    stmt = select(Empresa.id).where(func.lower(Empresa.nombre) == nombre.lower())
    if excepto:
        stmt = stmt.where(Empresa.id != excepto)
    if db.scalar(stmt):
        raise Conflicto(f"Ya existe una empresa llamada «{nombre}»")


def resumir(db: Session, empresas: list[Empresa]) -> list[dict[str, Any]]:
    """Agrega a cada empresa el número de cuentas activas, de proyectos y el saldo total por moneda."""
    ids = [e.id for e in empresas]
    if not ids:
        return []
    proyectos = dict(db.execute(select(EmpresaProyecto.empresa_id, func.count())
                                .where(EmpresaProyecto.empresa_id.in_(ids)).group_by(EmpresaProyecto.empresa_id)).all())
    cuentas = db.execute(select(Cuenta.id, Cuenta.empresa_id, Cuenta.moneda, Cuenta.activa)
                         .where(Cuenta.empresa_id.in_(ids))).all()
    saldos = saldos_cuentas(db, [c.id for c in cuentas])
    num_cuentas: dict[uuid.UUID, int] = defaultdict(int)
    por_moneda: dict[uuid.UUID, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for c in cuentas:
        num_cuentas[c.empresa_id] += int(c.activa)
        por_moneda[c.empresa_id][c.moneda] += saldos[c.id]
    return [
        {
            **EmpresaOut.model_validate(e).model_dump(),
            "num_cuentas": num_cuentas[e.id],
            "num_proyectos": proyectos.get(e.id, 0),
            "saldos": [{"moneda": m, "saldo": s} for m, s in sorted(por_moneda[e.id].items())],
        }
        for e in empresas
    ]


@router.get("", response_model=Pagina[EmpresaResumen])
def listar(db: DB, _: UsuarioActual, pag: PaginacionDep, q: str | None = None,
           activa: Annotated[bool | None, Query()] = None):
    stmt = select(Empresa).order_by(Empresa.nombre)
    if q:
        stmt = stmt.where(Empresa.nombre.ilike(f"%{q.strip()}%"))
    if activa is not None:
        stmt = stmt.where(Empresa.activa.is_(activa))
    pagina = paginar(db, stmt, pag.limit, pag.offset)
    pagina["items"] = resumir(db, pagina["items"])
    return pagina


@router.post("", response_model=EmpresaOut, status_code=status.HTTP_201_CREATED)
def crear(datos: EmpresaCrear, db: DB, usuario: UsuarioActual):
    """Solo se necesita el nombre; las cuentas se agregan después cuando se quiera."""
    _nombre_libre(db, datos.nombre)
    empresa = Empresa(nombre=datos.nombre, creado_por=usuario.id)
    db.add(empresa)
    db.flush()
    registrar(db, usuario_id=usuario.id, entidad="Empresa", entidad_id=empresa.id, accion=AccionBitacora.CREAR,
              detalle={"nombre": empresa.nombre})
    db.commit()
    return empresa


@router.get("/{empresa_id}", response_model=EmpresaResumen)
def obtener_una(empresa_id: uuid.UUID, db: DB, _: UsuarioActual):
    return resumir(db, [obtener(db, Empresa, empresa_id, "Empresa")])[0]


@router.patch("/{empresa_id}", response_model=EmpresaOut)
def actualizar(empresa_id: uuid.UUID, datos: EmpresaActualizar, db: DB, usuario: UsuarioActual):
    empresa = obtener(db, Empresa, empresa_id, "Empresa")
    verificar_autor(usuario, empresa)
    _nombre_libre(db, datos.nombre, excepto=empresa.id)
    antes = empresa.nombre
    empresa.nombre = datos.nombre
    registrar(db, usuario_id=usuario.id, entidad="Empresa", entidad_id=empresa.id, accion=AccionBitacora.EDITAR,
              detalle={"antes": {"nombre": antes}, "despues": {"nombre": empresa.nombre}})
    db.commit()
    return empresa


def _cambiar_estado(db: Session, empresa_id: uuid.UUID, usuario, activa: bool) -> Empresa:
    empresa = obtener(db, Empresa, empresa_id, "Empresa")
    verificar_autor(usuario, empresa)
    if empresa.activa != activa:
        empresa.activa = activa
        registrar(db, usuario_id=usuario.id, entidad="Empresa", entidad_id=empresa.id,
                  accion=AccionBitacora.ACTIVAR if activa else AccionBitacora.DESACTIVAR,
                  detalle={"nombre": empresa.nombre})
        db.commit()
    return empresa


@router.post("/{empresa_id}/activar", response_model=EmpresaOut)
def activar(empresa_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    return _cambiar_estado(db, empresa_id, usuario, True)


@router.post("/{empresa_id}/desactivar", response_model=EmpresaOut)
def desactivar(empresa_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    """Ya no se puede capturar en sus cuentas. Sus movimientos y saldos se conservan."""
    return _cambiar_estado(db, empresa_id, usuario, False)
