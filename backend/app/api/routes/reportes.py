import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response
from fastapi.responses import JSONResponse

from app.api.deps import DB, UsuarioActual
from app.core.errors import ReglaNegocio
from app.core.tiempo import hoy
from app.models import Moneda, Proyecto, Usuario
from app.schemas.reporte import ReporteOut
from app.services import reportes as svc
from app.services.acceso import obtener
from app.services.exportacion import MEDIA, Formato, Reporte, exportar
from app.services.reportes import AgruparGastos, AgruparIngresos
from app.services.serializacion import a_json

router = APIRouter(prefix="/reportes", tags=["Reportes"])

FormatoQ = Annotated[Formato, Query(description="json, csv, xlsx o pdf")]
DOC = {"response_model": ReporteOut, "responses": {200: {"content": {m: {} for m in MEDIA.values()}}}}


def responder(reporte: Reporte, formato: Formato, nombre: str, usuario: Usuario) -> Response:
    reporte.elaborado_por = usuario.nombre
    if formato == Formato.JSON:
        return JSONResponse(a_json({
            "titulo": reporte.titulo,
            "parametros": reporte.parametros,
            "columnas": [{"clave": c, "etiqueta": e} for c, e in reporte.columnas],
            "filas": reporte.filas,
            "totales": reporte.totales,
            "elaborado_por": reporte.elaborado_por,
            "estilo": reporte.estilo,
        }))
    return Response(
        content=exportar(reporte, formato),
        media_type=MEDIA[formato],
        headers={"Content-Disposition": f'attachment; filename="{nombre}-{hoy().isoformat()}.{formato.value}"'},
    )


def _validar_periodo(desde: date | None, hasta: date | None) -> None:
    if desde and hasta and desde > hasta:
        raise ReglaNegocio("La fecha inicial no puede ser posterior a la final")


@router.get("/resumen", summary="Dinero disponible por moneda (pantalla de inicio)")
def resumen(db: DB, _: UsuarioActual) -> dict[str, Any]:
    return a_json(svc.resumen(db))


@router.get("/saldos-proyectos", **DOC, summary="Saldo por proyecto")
def saldos_proyectos(db: DB, usuario: UsuarioActual, formato: FormatoQ = Formato.JSON, desde: date | None = None,
                     hasta: date | None = None, empresa_id: uuid.UUID | None = None,
                     proyecto_id: uuid.UUID | None = None, por_empresa: bool = False):
    """Con `por_empresa=true`, cuánto tiene cada proyecto en cada empresa (de ahí puede salir su dinero)."""
    _validar_periodo(desde, hasta)
    reporte = svc.saldos_proyectos(db, desde=desde, hasta=hasta, empresa_id=empresa_id, proyecto_id=proyecto_id,
                                   por_empresa=por_empresa)
    return responder(reporte, formato, "saldos-proyectos", usuario)


@router.get("/cuadre", **DOC, summary="Cuadre: saldo de las cuentas contra entradas, salidas y proyectos")
def cuadre(db: DB, usuario: UsuarioActual, formato: FormatoQ = Formato.JSON, hasta: date | None = None,
           empresa_id: uuid.UUID | None = None):
    """Por empresa y moneda, al corte `hasta` (por defecto, hoy)."""
    return responder(svc.cuadre(db, hasta=hasta, empresa_id=empresa_id), formato, "cuadre", usuario)


@router.get("/historial-proyecto/{proyecto_id}", **DOC, summary="Historial de un proyecto")
def historial_proyecto(proyecto_id: uuid.UUID, db: DB, usuario: UsuarioActual, formato: FormatoQ = Formato.JSON,
                       desde: date | None = None, hasta: date | None = None, empresa_id: uuid.UUID | None = None):
    _validar_periodo(desde, hasta)
    proyecto = obtener(db, Proyecto, proyecto_id, "Proyecto")
    reporte = svc.historial_proyecto(db, proyecto, desde=desde, hasta=hasta, empresa_id=empresa_id)
    return responder(reporte, formato, "historial-proyecto", usuario)


@router.get("/saldos-cuentas", **DOC, summary="Saldo por cuenta (cajas y bancos)")
def saldos_cuentas(db: DB, usuario: UsuarioActual, formato: FormatoQ = Formato.JSON, desde: date | None = None,
                   hasta: date | None = None, empresa_id: uuid.UUID | None = None, moneda: Moneda | None = None,
                   incluir_inactivas: bool = False):
    _validar_periodo(desde, hasta)
    reporte = svc.saldos_por_cuenta(db, desde=desde, hasta=hasta, empresa_id=empresa_id, moneda=moneda,
                                    incluir_inactivas=incluir_inactivas)
    return responder(reporte, formato, "saldos-cuentas", usuario)


@router.get("/gastos", **DOC, summary="Gastos por proyecto, por empresa o acumulados")
def gastos(db: DB, usuario: UsuarioActual, agrupar: AgruparGastos = AgruparGastos.PROYECTO,
           formato: FormatoQ = Formato.JSON, desde: date | None = None, hasta: date | None = None,
           empresa_id: uuid.UUID | None = None, proyecto_id: uuid.UUID | None = None):
    _validar_periodo(desde, hasta)
    reporte = svc.gastos(db, agrupar=agrupar, desde=desde, hasta=hasta, empresa_id=empresa_id,
                         proyecto_id=proyecto_id)
    return responder(reporte, formato, f"gastos-{agrupar.value}", usuario)


@router.get("/ingresos", **DOC, summary="Ingresos (neto) por proyecto o por empresa")
def ingresos(db: DB, usuario: UsuarioActual, agrupar: AgruparIngresos = AgruparIngresos.PROYECTO,
             formato: FormatoQ = Formato.JSON, desde: date | None = None, hasta: date | None = None,
             empresa_id: uuid.UUID | None = None, proyecto_id: uuid.UUID | None = None):
    _validar_periodo(desde, hasta)
    reporte = svc.ingresos(db, agrupar=agrupar, desde=desde, hasta=hasta, empresa_id=empresa_id,
                           proyecto_id=proyecto_id)
    return responder(reporte, formato, f"ingresos-{agrupar.value}", usuario)


@router.get("/por-categoria", **DOC, summary="Entradas y salidas por categoría")
def por_categoria(db: DB, usuario: UsuarioActual, formato: FormatoQ = Formato.JSON, desde: date | None = None,
                  hasta: date | None = None, empresa_id: uuid.UUID | None = None,
                  proyecto_id: uuid.UUID | None = None, por_proyecto: bool = False):
    """Con `por_proyecto=true`, una fila por proyecto y categoría."""
    _validar_periodo(desde, hasta)
    reporte = svc.por_categoria(db, desde=desde, hasta=hasta, empresa_id=empresa_id, proyecto_id=proyecto_id,
                                por_proyecto=por_proyecto)
    return responder(reporte, formato, "por-categoria", usuario)


@router.get("/estimado-vs-real", **DOC, summary="Proyecciones del proyecto contra lo real")
def estimado_vs_real(db: DB, usuario: UsuarioActual, formato: FormatoQ = Formato.JSON,
                     proyecto_id: uuid.UUID | None = None, solo_con_estimados: bool = False,
                     por_categoria: bool = False):
    """Con `por_categoria`, las partidas estimadas de cada categoría contra lo real de esa categoría."""
    if por_categoria:
        reporte = svc.estimado_vs_real_por_categoria(db, proyecto_id=proyecto_id)
        return responder(reporte, formato, "estimado-vs-real-por-categoria", usuario)
    reporte = svc.estimado_vs_real(db, proyecto_id=proyecto_id, solo_con_estimados=solo_con_estimados)
    return responder(reporte, formato, "estimado-vs-real", usuario)


@router.get("/cuentas-por-cobrar-pagar", **DOC, summary="Cuentas por cobrar y por pagar de los proyectos")
def cuentas_por_cobrar_pagar(db: DB, usuario: UsuarioActual, formato: FormatoQ = Formato.JSON,
                             proyecto_id: uuid.UUID | None = None, incluir_liquidadas: bool = False):
    reporte = svc.cuentas_por_cobrar_pagar(db, proyecto_id=proyecto_id, incluir_liquidadas=incluir_liquidadas)
    return responder(reporte, formato, "cuentas-por-cobrar-pagar", usuario)
