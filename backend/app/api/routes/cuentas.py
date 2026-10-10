import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import DB, UsuarioActual
from app.core.errors import Conflicto, ReglaNegocio
from app.models import AccionBitacora, Cuenta, Empresa, Moneda, TipoCuenta
from app.schemas.empresa import CuentaActualizar, CuentaConSaldo, CuentaCrear
from app.services.acceso import obtener, verificar_autor
from app.services.bitacora import instantanea, registrar
from app.services.saldos import saldos_cuentas

router = APIRouter(prefix="/cuentas", tags=["Cuentas"])

CAMPOS = ("empresa_id", "tipo", "moneda", "nombre", "banco", "numero", "activa")


def _nombre_libre(db: Session, empresa_id: uuid.UUID, nombre: str, excepto: uuid.UUID | None = None) -> None:
    stmt = select(Cuenta.id).where(Cuenta.empresa_id == empresa_id, func.lower(Cuenta.nombre) == nombre.lower())
    if excepto:
        stmt = stmt.where(Cuenta.id != excepto)
    if db.scalar(stmt):
        raise Conflicto(f"La empresa ya tiene una cuenta llamada «{nombre}»")


def con_saldo(db: Session, cuentas: list[Cuenta]) -> list[CuentaConSaldo]:
    saldos = saldos_cuentas(db, [c.id for c in cuentas]) if cuentas else {}
    campos = [c for c in CuentaConSaldo.model_fields if c != "saldo"]
    return [CuentaConSaldo(**{campo: getattr(c, campo) for campo in campos}, saldo=saldos[c.id]) for c in cuentas]


@router.get("", response_model=list[CuentaConSaldo], summary="Cuentas con su saldo actual")
def listar(db: DB, _: UsuarioActual, empresa_id: uuid.UUID | None = None, moneda: Moneda | None = None,
           tipo: TipoCuenta | None = None, activa: Annotated[bool | None, Query()] = None):
    stmt = select(Cuenta).join(Cuenta.empresa).order_by(Empresa.nombre, Cuenta.tipo, Cuenta.moneda, Cuenta.nombre)
    if empresa_id:
        stmt = stmt.where(Cuenta.empresa_id == empresa_id)
    if moneda:
        stmt = stmt.where(Cuenta.moneda == moneda)
    if tipo:
        stmt = stmt.where(Cuenta.tipo == tipo)
    if activa is not None:
        stmt = stmt.where(Cuenta.activa.is_(activa))
    return con_saldo(db, list(db.scalars(stmt).unique()))


@router.post("", response_model=CuentaConSaldo, status_code=status.HTTP_201_CREATED)
def crear(datos: CuentaCrear, db: DB, usuario: UsuarioActual):
    """Cuenta de banco (varias por empresa) o caja de efectivo (una por moneda). La moneda ya no se cambia."""
    empresa = obtener(db, Empresa, datos.empresa_id, "Empresa")
    if not empresa.activa:
        raise ReglaNegocio(f"La empresa «{empresa.nombre}» está desactivada")
    if datos.tipo == TipoCuenta.CAJA and db.scalar(select(Cuenta.id).where(
            Cuenta.empresa_id == empresa.id, Cuenta.tipo == TipoCuenta.CAJA, Cuenta.moneda == datos.moneda)):
        raise Conflicto(f"{empresa.nombre} ya tiene una caja en {datos.moneda}")
    nombre = datos.nombre or (f"Caja {datos.moneda}" if datos.tipo == TipoCuenta.CAJA
                              else f"{datos.banco or 'Banco'} {datos.moneda}")
    _nombre_libre(db, empresa.id, nombre)
    cuenta = Cuenta(**datos.model_dump(exclude={"nombre"}), nombre=nombre, creado_por=usuario.id)
    db.add(cuenta)
    db.flush()
    db.refresh(cuenta)
    registrar(db, usuario_id=usuario.id, entidad="Cuenta", entidad_id=cuenta.id, accion=AccionBitacora.CREAR,
              detalle={"empresa": empresa.nombre, "despues": instantanea(cuenta, CAMPOS)})
    db.commit()
    return con_saldo(db, [cuenta])[0]


@router.get("/{cuenta_id}", response_model=CuentaConSaldo)
def obtener_una(cuenta_id: uuid.UUID, db: DB, _: UsuarioActual):
    return con_saldo(db, [obtener(db, Cuenta, cuenta_id, "Cuenta")])[0]


@router.patch("/{cuenta_id}", response_model=CuentaConSaldo)
def actualizar(cuenta_id: uuid.UUID, datos: CuentaActualizar, db: DB, usuario: UsuarioActual):
    """Nombre, banco y número. La empresa, el tipo y la moneda no se pueden cambiar."""
    cuenta = obtener(db, Cuenta, cuenta_id, "Cuenta")
    verificar_autor(usuario, cuenta)
    cambios = datos.model_dump(exclude_unset=True)
    if not cambios:
        raise ReglaNegocio("No se indicó ningún cambio")
    if "nombre" in cambios:
        if cambios["nombre"] is None:
            raise ReglaNegocio("El nombre no puede quedar vacío")
        _nombre_libre(db, cuenta.empresa_id, cambios["nombre"], excepto=cuenta.id)
    antes = instantanea(cuenta, CAMPOS)
    for campo, valor in cambios.items():
        setattr(cuenta, campo, valor)
    registrar(db, usuario_id=usuario.id, entidad="Cuenta", entidad_id=cuenta.id, accion=AccionBitacora.EDITAR,
              detalle={"antes": antes, "despues": instantanea(cuenta, CAMPOS)})
    db.commit()
    return con_saldo(db, [cuenta])[0]


def _cambiar_estado(db: Session, cuenta_id: uuid.UUID, usuario, activa: bool) -> list[CuentaConSaldo]:
    cuenta = obtener(db, Cuenta, cuenta_id, "Cuenta")
    verificar_autor(usuario, cuenta)
    if cuenta.activa != activa:
        if not activa:
            saldo = saldos_cuentas(db, [cuenta.id])[cuenta.id]
            if saldo != 0:
                raise ReglaNegocio(f"La cuenta tiene saldo ({saldo:,.2f} {cuenta.moneda}); "
                                   "debe quedar en cero antes de desactivarla")
        cuenta.activa = activa
        registrar(db, usuario_id=usuario.id, entidad="Cuenta", entidad_id=cuenta.id,
                  accion=AccionBitacora.ACTIVAR if activa else AccionBitacora.DESACTIVAR,
                  detalle={"cuenta": cuenta.nombre, "empresa": cuenta.empresa.nombre})
        db.commit()
    return con_saldo(db, [cuenta])


@router.post("/{cuenta_id}/activar", response_model=CuentaConSaldo)
def activar(cuenta_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    return _cambiar_estado(db, cuenta_id, usuario, True)[0]


@router.post("/{cuenta_id}/desactivar", response_model=CuentaConSaldo)
def desactivar(cuenta_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    """Solo con saldo en cero. Ya no se puede capturar en ella."""
    return _cambiar_estado(db, cuenta_id, usuario, False)[0]
