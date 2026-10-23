import uuid
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import DB, PaginacionDep, UsuarioActual
from app.api.utils import paginar
from app.core.errors import Conflicto, NoEncontrado, ReglaNegocio
from app.models import AccionBitacora, Empresa, EmpresaProyecto, Entrada, Moneda, Proyecto, Salida
from app.schemas.comun import Pagina
from app.schemas.empresa import (
    CAMPOS_PROYECCION,
    ProyectoActualizar,
    ProyectoCrear,
    ProyectoOut,
    ProyectoResumen,
    SaldoProyecto,
    SaldoProyectoEmpresa,
    Vincular,
)
from app.services.acceso import obtener, verificar_autor
from app.services.bitacora import instantanea, registrar
from app.services import proyecciones
from app.services.movimientos import vincular
from app.services.saldos import TotalesProyecto, totales_por_empresa

router = APIRouter(prefix="/proyectos", tags=["Proyectos"])

CAMPOS = ("nombre", "descripcion", *CAMPOS_PROYECCION)


def _nombre_libre(db: Session, nombre: str, excepto: uuid.UUID | None = None) -> None:
    stmt = select(Proyecto.id).where(func.lower(Proyecto.nombre) == nombre.lower())
    if excepto:
        stmt = stmt.where(Proyecto.id != excepto)
    if db.scalar(stmt):
        raise Conflicto(f"Ya existe un proyecto llamado «{nombre}»")


def resumir(db: Session, proyectos: list[Proyecto]) -> list[ProyectoResumen]:
    """Agrega a cada proyecto sus ingresos (neto), gastos, salidas y saldo por moneda, en total y por empresa."""
    por_empresa = totales_por_empresa(db, [p.id for p in proyectos]) if proyectos else {}
    nombres = dict(db.execute(select(Empresa.id, Empresa.nombre)
                              .where(Empresa.id.in_({e for _, e, _ in por_empresa}))).all()) if por_empresa else {}
    resultado = []
    for p in proyectos:
        detalle = sorted(((eid, m, t) for (pid, eid, m), t in por_empresa.items() if pid == p.id),
                         key=lambda x: (nombres[x[0]].lower(), x[1]))
        total: dict[Moneda, TotalesProyecto] = defaultdict(TotalesProyecto)
        for _, m, t in detalle:
            total[m] += t
        resultado.append(ProyectoResumen(
            **ProyectoOut.model_validate(p).model_dump(),
            saldos=[SaldoProyecto(moneda=m, ingresos=t.ingresos, gastos=t.gastos, salidas=t.salidas, saldo=t.saldo)
                    for m, t in sorted(total.items())],
            saldos_por_empresa=[SaldoProyectoEmpresa(empresa_id=eid, empresa_nombre=nombres[eid], moneda=m,
                                                     ingresos=t.ingresos, gastos=t.gastos, salidas=t.salidas,
                                                     saldo=t.saldo) for eid, m, t in detalle],
        ))
    return resultado


def _obtener(db: Session, proyecto_id: uuid.UUID) -> Proyecto:
    return obtener(db, Proyecto, proyecto_id, "Proyecto")


@router.get("", response_model=Pagina[ProyectoResumen])
def listar(db: DB, _: UsuarioActual, pag: PaginacionDep, q: str | None = None, empresa_id: uuid.UUID | None = None,
           activo: Annotated[bool | None, Query()] = None):
    stmt = select(Proyecto).options(selectinload(Proyecto.empresas)).order_by(Proyecto.nombre)
    if q:
        stmt = stmt.where(Proyecto.nombre.ilike(f"%{q.strip()}%"))
    if empresa_id:
        stmt = stmt.where(exists().where(EmpresaProyecto.proyecto_id == Proyecto.id,
                                         EmpresaProyecto.empresa_id == empresa_id))
    if activo is not None:
        stmt = stmt.where(Proyecto.activo.is_(activo))
    pagina = paginar(db, stmt, pag.limit, pag.offset)
    pagina["items"] = resumir(db, pagina["items"])
    return pagina


@router.post("", response_model=ProyectoResumen, status_code=status.HTTP_201_CREATED)
def crear(datos: ProyectoCrear, db: DB, usuario: UsuarioActual):
    """Solo se necesita el nombre. Las empresas se vinculan solas al capturar entradas o salidas."""
    _nombre_libre(db, datos.nombre)
    proyecto = Proyecto(**datos.model_dump(exclude={"empresa_ids", "partidas"}), creado_por=usuario.id)
    db.add(proyecto)
    db.flush()
    # Con partidas, los totales estimados son su suma.
    for partida in datos.partidas:
        proyecciones.agregar(db, proyecto, partida, usuario)
    if datos.partidas:
        proyecciones.recalcular(db, proyecto)
    registrar(db, usuario_id=usuario.id, entidad="Proyecto", entidad_id=proyecto.id, accion=AccionBitacora.CREAR,
              detalle={"despues": instantanea(proyecto, CAMPOS), "partidas_estimadas": len(datos.partidas)})
    for empresa_id in dict.fromkeys(datos.empresa_ids):
        vincular(db, obtener(db, Empresa, empresa_id, "Empresa"), proyecto, usuario, automatico=False)
    db.commit()
    db.refresh(proyecto)
    return resumir(db, [proyecto])[0]


@router.get("/{proyecto_id}", response_model=ProyectoResumen)
def obtener_uno(proyecto_id: uuid.UUID, db: DB, _: UsuarioActual):
    return resumir(db, [_obtener(db, proyecto_id)])[0]


@router.patch("/{proyecto_id}", response_model=ProyectoResumen)
def actualizar(proyecto_id: uuid.UUID, datos: ProyectoActualizar, db: DB, usuario: UsuarioActual):
    proyecto = _obtener(db, proyecto_id)
    verificar_autor(usuario, proyecto)
    cambios = datos.model_dump(exclude_unset=True)
    if not cambios:
        raise ReglaNegocio("No se indicó ningún cambio")
    if "nombre" in cambios:
        if cambios["nombre"] is None:
            raise ReglaNegocio("El nombre no puede quedar vacío")
        _nombre_libre(db, cambios["nombre"], excepto=proyecto.id)
    proyecciones.validar_estimados_manuales(proyecto, cambios)
    antes = instantanea(proyecto, CAMPOS)
    for campo, valor in cambios.items():
        setattr(proyecto, campo, valor)
    if proyecto.fecha_inicio_estimada and proyecto.fecha_fin_estimada             and proyecto.fecha_fin_estimada < proyecto.fecha_inicio_estimada:
        raise ReglaNegocio("La fecha estimada de terminación no puede ser anterior a la de inicio")
    registrar(db, usuario_id=usuario.id, entidad="Proyecto", entidad_id=proyecto.id, accion=AccionBitacora.EDITAR,
              detalle={"antes": antes, "despues": instantanea(proyecto, CAMPOS)})
    db.commit()
    return resumir(db, [proyecto])[0]


def _cambiar_estado(db: Session, proyecto_id: uuid.UUID, usuario, activo: bool) -> ProyectoResumen:
    proyecto = _obtener(db, proyecto_id)
    verificar_autor(usuario, proyecto)
    if proyecto.activo != activo:
        proyecto.activo = activo
        registrar(db, usuario_id=usuario.id, entidad="Proyecto", entidad_id=proyecto.id,
                  accion=AccionBitacora.ACTIVAR if activo else AccionBitacora.DESACTIVAR,
                  detalle={"nombre": proyecto.nombre})
        db.commit()
    return resumir(db, [proyecto])[0]


@router.post("/{proyecto_id}/activar", response_model=ProyectoResumen)
def activar(proyecto_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    return _cambiar_estado(db, proyecto_id, usuario, True)


@router.post("/{proyecto_id}/desactivar", response_model=ProyectoResumen)
def desactivar(proyecto_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    """Ya no se le pueden capturar entradas ni salidas. Su historial se conserva."""
    return _cambiar_estado(db, proyecto_id, usuario, False)


@router.post("/{proyecto_id}/empresas", response_model=ProyectoResumen, summary="Vincular una empresa")
def vincular_empresa(proyecto_id: uuid.UUID, datos: Vincular, db: DB, usuario: UsuarioActual):
    proyecto = _obtener(db, proyecto_id)
    empresa = obtener(db, Empresa, datos.empresa_id, "Empresa")
    if not vincular(db, empresa, proyecto, usuario, automatico=False):
        raise Conflicto(f"«{empresa.nombre}» ya está vinculada al proyecto")
    db.commit()
    db.refresh(proyecto)
    return resumir(db, [proyecto])[0]


@router.delete("/{proyecto_id}/empresas/{empresa_id}", response_model=ProyectoResumen,
               summary="Desvincular una empresa (solo si no tiene movimientos del proyecto)")
def desvincular_empresa(proyecto_id: uuid.UUID, empresa_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    proyecto = _obtener(db, proyecto_id)
    vinculo = db.get(EmpresaProyecto, (empresa_id, proyecto_id))
    if vinculo is None:
        raise NoEncontrado("La empresa no está vinculada al proyecto")
    if not usuario.es_admin and vinculo.creado_por != usuario.id:
        verificar_autor(usuario, proyecto)
    for modelo in (Entrada, Salida):
        if db.scalar(select(modelo.id).where(modelo.proyecto_id == proyecto_id, modelo.empresa_id == empresa_id)
                     .limit(1)):
            raise ReglaNegocio("La empresa tiene movimientos de este proyecto (aunque estén anulados); "
                               "no se puede desvincular")
    empresa = obtener(db, Empresa, empresa_id, "Empresa")
    db.delete(vinculo)
    registrar(db, usuario_id=usuario.id, entidad="Proyecto", entidad_id=proyecto.id, accion=AccionBitacora.DESVINCULAR,
              detalle={"empresa_id": empresa.id, "empresa": empresa.nombre, "proyecto": proyecto.nombre})
    db.commit()
    db.refresh(proyecto)
    return resumir(db, [proyecto])[0]
