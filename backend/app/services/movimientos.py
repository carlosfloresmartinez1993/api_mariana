"""Reglas de entradas y salidas.

- La cuenta debe ser de la empresa indicada y estar activa; efectivo → caja, transferencia → banco.
- La empresa se vincula al proyecto automáticamente si aún no lo estaba.
- Un proyecto puede quedar en negativo: si tuvo pérdida, se paga con dinero de otros proyectos que está en
  la misma cuenta. La cuenta sí debe alcanzar (es dinero físico): después de cada alta, edición o anulación
  ninguna cuenta puede quedar en negativo.
- Nada se borra: se anula con motivo. Todo queda en la bitácora.
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.api.utils import validar_no_futura
from app.core.errors import ReglaNegocio
from app.core.tiempo import ahora
from app.models import AccionBitacora, Cuenta, Empresa, EmpresaProyecto, Entrada, Forma, Proyecto, Salida, Usuario
from app.schemas.movimiento import EntradaCrear, SalidaCrear
from app.services.acceso import obtener, verificar_autor
from app.services.bitacora import instantanea, registrar
from app.services.saldos import bloquear, validar_no_negativos

CAMPOS_ENTRADA = ("proyecto_id", "empresa_id", "cuenta_id", "moneda", "fecha", "forma", "monto", "porcentaje_gasto",
                  "monto_gasto", "monto_neto", "concepto", "referencia", "requiere_factura")
CAMPOS_SALIDA = ("proyecto_id", "empresa_id", "cuenta_id", "moneda", "fecha", "forma", "monto", "concepto",
                 "beneficiario", "requiere_factura")
Movimiento = Entrada | Salida


def _activa(cuenta: Cuenta) -> Cuenta:
    if not cuenta.activa:
        raise ReglaNegocio(f"La cuenta «{cuenta.nombre}» está desactivada")
    if not cuenta.empresa.activa:
        raise ReglaNegocio(f"La empresa «{cuenta.empresa.nombre}» está desactivada")
    return cuenta


def _cuenta_de_empresa(db: Session, cuenta_id: uuid.UUID, empresa_id: uuid.UUID, forma: Forma) -> Cuenta:
    cuenta = _activa(obtener(db, Cuenta, cuenta_id, "Cuenta"))
    if cuenta.empresa_id != empresa_id:
        raise ReglaNegocio(f"La cuenta «{cuenta.nombre}» no es de la empresa elegida")
    if cuenta.tipo != forma.tipo_cuenta:
        raise ReglaNegocio("El efectivo va a una caja y las transferencias a una cuenta de banco")
    return cuenta


def _proyecto_activo(db: Session, proyecto_id: uuid.UUID) -> Proyecto:
    proyecto = obtener(db, Proyecto, proyecto_id, "Proyecto")
    if not proyecto.activo:
        raise ReglaNegocio(f"El proyecto «{proyecto.nombre}» está desactivado")
    return proyecto


def vincular(db: Session, empresa: Empresa, proyecto: Proyecto, usuario: Usuario, *, automatico: bool) -> bool:
    """Vincula la empresa al proyecto si no lo estaba. Devuelve True si creó el vínculo."""
    if db.get(EmpresaProyecto, (empresa.id, proyecto.id)):
        return False
    db.add(EmpresaProyecto(empresa_id=empresa.id, proyecto_id=proyecto.id, creado_por=usuario.id))
    registrar(db, usuario_id=usuario.id, entidad="Proyecto", entidad_id=proyecto.id, accion=AccionBitacora.VINCULAR,
              detalle={"empresa_id": empresa.id, "empresa": empresa.nombre, "proyecto": proyecto.nombre,
                       "automatico": automatico})
    db.flush()
    return True


# ------------------------------------------------------------------ altas
def crear_entrada(db: Session, datos: EntradaCrear, usuario: Usuario) -> Entrada:
    validar_no_futura(datos.fecha)
    proyecto = _proyecto_activo(db, datos.proyecto_id)
    cuenta = _cuenta_de_empresa(db, datos.cuenta_id, datos.empresa_id, datos.forma)
    vincular(db, cuenta.empresa, proyecto, usuario, automatico=True)
    entrada = Entrada(**datos.model_dump(), moneda=cuenta.moneda, creado_por=usuario.id)
    db.add(entrada)
    db.flush()
    db.refresh(entrada)  # trae monto_gasto y monto_neto calculados por la base de datos
    registrar(db, usuario_id=usuario.id, entidad="Entrada", entidad_id=entrada.id, accion=AccionBitacora.CREAR,
              detalle={"despues": instantanea(entrada, CAMPOS_ENTRADA)})
    db.commit()
    return entrada


def crear_salida(db: Session, datos: SalidaCrear, usuario: Usuario) -> Salida:
    validar_no_futura(datos.fecha)
    proyecto = _proyecto_activo(db, datos.proyecto_id)
    cuenta = _cuenta_de_empresa(db, datos.cuenta_id, datos.empresa_id, datos.forma)
    bloquear(db, proyecto_ids={proyecto.id}, cuenta_ids={cuenta.id})
    vincular(db, cuenta.empresa, proyecto, usuario, automatico=True)
    salida = Salida(**datos.model_dump(), moneda=cuenta.moneda, creado_por=usuario.id)
    db.add(salida)
    validar_no_negativos(db, cuenta_ids={cuenta.id})
    registrar(db, usuario_id=usuario.id, entidad="Salida", entidad_id=salida.id, accion=AccionBitacora.CREAR,
              detalle={"despues": instantanea(salida, CAMPOS_SALIDA)})
    db.commit()
    return salida


# ------------------------------------------------------------------ edición y anulación
def _campos(mov: Movimiento) -> tuple[str, tuple[str, ...]]:
    return ("Entrada", CAMPOS_ENTRADA) if isinstance(mov, Entrada) else ("Salida", CAMPOS_SALIDA)


def _validar_saldos(db: Session, mov: Movimiento) -> None:
    validar_no_negativos(db, cuenta_ids={mov.cuenta_id})


def editar(db: Session, mov: Movimiento, cambios: dict[str, Any], usuario: Usuario) -> Movimiento:
    verificar_autor(usuario, mov)
    if mov.anulado:
        raise ReglaNegocio("No se puede editar un movimiento anulado")
    if not cambios:
        raise ReglaNegocio("No se indicó ningún cambio")
    if cambios.get("fecha"):
        validar_no_futura(cambios["fecha"])
    obligatorios = {"fecha", "monto", "porcentaje_gasto", "requiere_factura",
                    "concepto" if isinstance(mov, Salida) else ""}
    if nulos := sorted(c for c in obligatorios if c in cambios and cambios[c] is None):
        raise ReglaNegocio(f"Estos campos no pueden quedar vacíos: {', '.join(nulos)}")
    entidad, campos = _campos(mov)
    bloquear(db, proyecto_ids={mov.proyecto_id}, cuenta_ids={mov.cuenta_id})
    antes = instantanea(mov, campos)
    for campo, valor in cambios.items():
        setattr(mov, campo, valor)
    _validar_saldos(db, mov)
    db.refresh(mov)
    registrar(db, usuario_id=usuario.id, entidad=entidad, entidad_id=mov.id, accion=AccionBitacora.EDITAR,
              detalle={"antes": antes, "despues": instantanea(mov, campos)})
    db.commit()
    return mov


def anular(db: Session, mov: Movimiento, motivo: str, usuario: Usuario) -> Movimiento:
    """Deja de contar en los saldos. No se permite si la cuenta o el proyecto (en esa empresa) quedaría en negativo."""
    verificar_autor(usuario, mov)
    if mov.anulado:
        raise ReglaNegocio("El movimiento ya está anulado")
    entidad, campos = _campos(mov)
    bloquear(db, proyecto_ids={mov.proyecto_id}, cuenta_ids={mov.cuenta_id})
    mov.anulado = True
    mov.motivo_anulacion = motivo
    mov.anulado_por = usuario.id
    mov.fecha_anulacion = ahora()
    _validar_saldos(db, mov)
    registrar(db, usuario_id=usuario.id, entidad=entidad, entidad_id=mov.id, accion=AccionBitacora.ANULAR,
              detalle={"motivo": motivo, "antes": instantanea(mov, campos)})
    db.commit()
    return mov

