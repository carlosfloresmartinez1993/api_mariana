"""Reportes. Todos cuentan solo movimientos vigentes, separan por moneda y aceptan un periodo opcional
(sin periodo = todo el historial). Los ingresos son siempre el neto que llegó a la cuenta.
"""

import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Cuenta, Empresa, Entrada, Moneda, Proyecto, Salida, TipoCuenta
from app.services.exportacion import Reporte
from app.services.saldos import (
    CERO,
    TotalesProyecto,
    saldos_cuentas,
    totales_por_empresa,
    totales_proyectos,
)
from app.services.saldos import cuadre as calcular_cuadre


class AgruparGastos(StrEnum):
    PROYECTO = "proyecto"
    EMPRESA = "empresa"
    MONEDA = "moneda"  # gastos acumulados


class AgruparIngresos(StrEnum):
    PROYECTO = "proyecto"
    EMPRESA = "empresa"


def _parametros(desde: date | None, hasta: date | None, **otros: Any) -> dict[str, Any]:
    return {"Desde": desde or "inicio", "Hasta": hasta or "hoy", **{k: v for k, v in otros.items() if v is not None}}


def _periodo(stmt, columna, desde: date | None, hasta: date | None):
    if desde:
        stmt = stmt.where(columna >= desde)
    if hasta:
        stmt = stmt.where(columna <= hasta)
    return stmt


def _nombre(db: Session, modelo, id_: uuid.UUID | None) -> str | None:
    registro = db.get(modelo, id_) if id_ else None
    return registro.nombre if registro else None


def _totales_por_moneda(filas: list[dict[str, Any]], columnas: tuple[str, ...], etiqueta: str = "moneda"
                        ) -> list[dict[str, Any]]:
    suma: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: CERO))
    for f in filas:
        for c in columnas:
            suma[f["moneda"]][c] += f.get(c) or 0
    return [{etiqueta: f"TOTAL {m}", "moneda": m, **valores} for m, valores in sorted(suma.items())]


# ------------------------------------------------------------------ proyectos
def saldos_proyectos(db: Session, *, desde: date | None = None, hasta: date | None = None,
                     empresa_id: uuid.UUID | None = None, proyecto_id: uuid.UUID | None = None,
                     por_empresa: bool = False) -> Reporte:
    """Con `por_empresa`, una fila por proyecto, empresa y moneda: el dinero que el proyecto tiene en cada empresa."""
    totales = totales_por_empresa(db, [proyecto_id] if proyecto_id else None, empresa_id=empresa_id,
                                  desde=desde, hasta=hasta)
    proyectos = dict(db.execute(select(Proyecto.id, Proyecto.nombre)
                                .where(Proyecto.id.in_({p for p, _, _ in totales}))).all())
    empresas = dict(db.execute(select(Empresa.id, Empresa.nombre).where(Empresa.id.in_({e for _, e, _ in totales}))).all())
    agrupados: dict[tuple, TotalesProyecto] = defaultdict(TotalesProyecto)
    for (pid, eid, m), t in totales.items():
        agrupados[(proyectos[pid], empresas[eid] if por_empresa else None, m)] += t
    filas = sorted(
        ({"proyecto": p, **({"empresa": e} if por_empresa else {}), "moneda": m, "ingresos": t.ingresos,
          "gastos": t.gastos, "salidas": t.salidas, "saldo": t.saldo} for (p, e, m), t in agrupados.items()),
        key=lambda f: (f["proyecto"].lower(), f.get("empresa", "").lower(), f["moneda"]),
    )
    return Reporte(
        titulo="Saldo por proyecto y empresa" if por_empresa else "Saldo por proyecto",
        columnas=[("proyecto", "Proyecto"), *([("empresa", "Empresa")] if por_empresa else []), ("moneda", "Moneda"),
                  ("ingresos", "Ingresos (neto)"), ("gastos", "Gastos"), ("salidas", "Salidas"), ("saldo", "Saldo")],
        filas=filas,
        totales=_totales_por_moneda(filas, ("ingresos", "gastos", "salidas", "saldo"), "proyecto"),
        parametros=_parametros(desde, hasta, Empresa=_nombre(db, Empresa, empresa_id)),
    )


def historial_proyecto(db: Session, proyecto: Proyecto, *, desde: date | None = None, hasta: date | None = None,
                       empresa_id: uuid.UUID | None = None) -> Reporte:
    """Todas las entradas y salidas del proyecto, con la cuenta a la que llegaron o de la que salieron,
    y el saldo acumulado por moneda. Con `desde`, empieza con el saldo anterior."""
    entradas = select(Entrada).where(Entrada.proyecto_id == proyecto.id, Entrada.anulado.is_(False))
    salidas = select(Salida).where(Salida.proyecto_id == proyecto.id, Salida.anulado.is_(False))
    if empresa_id:
        entradas = entradas.where(Entrada.empresa_id == empresa_id)
        salidas = salidas.where(Salida.empresa_id == empresa_id)

    saldo: dict[str, Decimal] = defaultdict(lambda: CERO)
    filas: list[dict[str, Any]] = []
    if desde:
        anteriores = totales_proyectos(db, [proyecto.id], empresa_id=empresa_id, hasta=desde - timedelta(days=1))
        for (_, moneda), t in sorted(anteriores.items(), key=lambda x: x[0][1]):
            saldo[moneda] = t.saldo
            filas.append({"fecha": desde, "tipo": "Saldo anterior", "moneda": moneda, "saldo": t.saldo})

    movimientos: list[tuple[date, int, Any]] = [
        (e.fecha, 0, e) for e in db.scalars(_periodo(entradas, Entrada.fecha, desde, hasta)).unique()
    ] + [(s.fecha, 1, s) for s in db.scalars(_periodo(salidas, Salida.fecha, desde, hasta)).unique()]
    movimientos.sort(key=lambda m: (m[0], m[1], m[2].fecha_creacion))

    for _, _, mov in movimientos:
        comun = {"fecha": mov.fecha, "empresa": mov.empresa.nombre, "cuenta": mov.cuenta.nombre,
                 "moneda": mov.moneda, "forma": mov.forma, "registrado_por": mov.creado_por_nombre}
        if isinstance(mov, Entrada):
            saldo[mov.moneda] += mov.monto_neto
            filas.append({**comun, "tipo": "Entrada", "concepto": mov.concepto or mov.referencia, "bruto": mov.monto,
                          "porcentaje": mov.porcentaje_gasto, "gasto": mov.monto_gasto, "entrada": mov.monto_neto,
                          "saldo": saldo[mov.moneda]})
        else:
            saldo[mov.moneda] -= mov.monto
            concepto = f"{mov.concepto} — {mov.beneficiario}" if mov.beneficiario else mov.concepto
            filas.append({**comun, "tipo": "Salida", "concepto": concepto, "salida": mov.monto,
                          "saldo": saldo[mov.moneda]})

    movs = [f for f in filas if f["tipo"] != "Saldo anterior"]
    totales = _totales_por_moneda(movs, ("bruto", "gasto", "entrada", "salida"), "fecha")
    for t in totales:
        t["saldo"] = saldo[t["moneda"]]
    return Reporte(
        titulo=f"Historial del proyecto {proyecto.nombre}",
        columnas=[("fecha", "Fecha"), ("tipo", "Tipo"), ("empresa", "Empresa"), ("cuenta", "Cuenta"),
                  ("moneda", "Moneda"), ("forma", "Forma"), ("concepto", "Concepto"), ("bruto", "Monto recibido"),
                  ("porcentaje", "% gasto"), ("gasto", "Gasto"), ("entrada", "Entrada (neto)"),
                  ("salida", "Salida"), ("saldo", "Saldo"), ("registrado_por", "Registrado por")],
        filas=filas,
        totales=totales,
        parametros=_parametros(desde, hasta, Proyecto=proyecto.nombre, Empresa=_nombre(db, Empresa, empresa_id)),
    )


# ------------------------------------------------------------------ cuentas
def saldos_por_cuenta(db: Session, *, desde: date | None = None, hasta: date | None = None,
                      empresa_id: uuid.UUID | None = None, moneda: Moneda | None = None,
                      incluir_inactivas: bool = False) -> Reporte:
    """Cuánto hay en cada cuenta de banco y en cada caja. Totales por moneda: cajas, bancos y total."""
    stmt = select(Cuenta).join(Cuenta.empresa).order_by(Empresa.nombre, Cuenta.moneda, Cuenta.tipo, Cuenta.nombre)
    if empresa_id:
        stmt = stmt.where(Cuenta.empresa_id == empresa_id)
    if moneda:
        stmt = stmt.where(Cuenta.moneda == moneda)
    if not incluir_inactivas:
        stmt = stmt.where(Cuenta.activa.is_(True))
    cuentas = list(db.scalars(stmt).unique())
    ids = [c.id for c in cuentas]

    anterior = saldos_cuentas(db, ids, hasta=desde - timedelta(days=1)) if desde else {c.id: CERO for c in cuentas}
    flujos: dict[str, dict[uuid.UUID, Decimal]] = {}
    for clave, modelo, col_cuenta, monto in (
        ("entradas", Entrada, Entrada.cuenta_id, Entrada.monto_neto),
        ("salidas", Salida, Salida.cuenta_id, Salida.monto),
    ):
        consulta = _periodo(select(col_cuenta, func.sum(monto)).where(modelo.anulado.is_(False), col_cuenta.in_(ids))
                            .group_by(col_cuenta), modelo.fecha, desde, hasta)
        flujos[clave] = {cid: Decimal(total) for cid, total in db.execute(consulta)} if ids else {}

    filas = []
    for c in cuentas:
        f = {"empresa": c.empresa.nombre, "cuenta": c.nombre, "tipo": "Caja" if c.tipo == TipoCuenta.CAJA else "Banco",
             "moneda": c.moneda, "anterior": anterior[c.id],
             **{k: flujos[k].get(c.id, CERO) for k in flujos}}
        f["saldo"] = f["anterior"] + f["entradas"] - f["salidas"]
        filas.append(f)

    columnas_suma = ("anterior", "entradas", "salidas", "saldo")
    totales = []
    for m in sorted({f["moneda"] for f in filas}):
        for etiqueta, tipo in (("Total cajas", "Caja"), ("Total bancos", "Banco"), ("TOTAL", None)):
            grupo = [f for f in filas if f["moneda"] == m and (tipo is None or f["tipo"] == tipo)]
            if grupo:
                totales.append({"empresa": f"{etiqueta} {m}", "moneda": m,
                                **{k: sum((f[k] for f in grupo), CERO) for k in columnas_suma}})
    return Reporte(
        titulo="Saldo por cuenta",
        columnas=[("empresa", "Empresa"), ("cuenta", "Cuenta"), ("tipo", "Tipo"), ("moneda", "Moneda"),
                  *([("anterior", "Saldo anterior")] if desde else []), ("entradas", "Entradas (neto)"),
                  ("salidas", "Salidas"), ("saldo", "Saldo")],
        filas=filas,
        totales=totales,
        parametros=_parametros(desde, hasta, Empresa=_nombre(db, Empresa, empresa_id), Moneda=moneda),
    )


def cuadre(db: Session, *, hasta: date | None = None, empresa_id: uuid.UUID | None = None) -> Reporte:
    """Comprueba por empresa y moneda que el dinero de las cuentas cuadra con los movimientos:
    entradas (neto) − salidas = saldo de las cuentas = saldo de los proyectos."""
    resultado = calcular_cuadre(db, hasta=hasta, empresa_id=empresa_id)
    nombres = dict(db.execute(select(Empresa.id, Empresa.nombre).where(Empresa.id.in_({e for e, _ in resultado}))).all())
    filas = sorted(
        ({"empresa": nombres[eid], "moneda": m, "entradas": c.entradas,
          "salidas": c.salidas, "cuentas": c.saldo_cuentas, "proyectos": c.saldo_proyectos,
          "diferencia": c.diferencia, "estado": "Cuadra" if c.diferencia == 0 else "NO CUADRA"}
         for (eid, m), c in resultado.items()),
        key=lambda f: (f["empresa"].lower(), f["moneda"]),
    )
    totales = _totales_por_moneda(filas, ("entradas", "salidas", "cuentas", "proyectos", "diferencia"),
                                  "empresa")
    for t in totales:
        t["estado"] = "Cuadra" if t["diferencia"] == 0 else "NO CUADRA"
    return Reporte(
        titulo="Cuadre de cuentas y proyectos",
        columnas=[("empresa", "Empresa"), ("moneda", "Moneda"), ("entradas", "Entradas (neto)"), ("salidas", "Salidas"), ("cuentas", "Saldo en cuentas"),
                  ("proyectos", "Saldo de proyectos"), ("diferencia", "Diferencia"), ("estado", "Estado")],
        filas=filas,
        totales=totales,
        parametros={"Al": hasta or "hoy", **({"Empresa": nombres.get(empresa_id)} if empresa_id else {})},
    )


# ------------------------------------------------------------------ gastos e ingresos
def _agrupado(db: Session, columna_valor, *, agrupar: str, desde: date | None, hasta: date | None,
              empresa_id: uuid.UUID | None, proyecto_id: uuid.UUID | None) -> list[dict[str, Any]]:
    grupo = {"proyecto": Proyecto.nombre, "empresa": Empresa.nombre}.get(agrupar)
    columnas = [grupo.label("grupo")] if grupo is not None else []
    stmt = (select(*columnas, Entrada.moneda, func.count(), func.sum(columna_valor))
            .join(Proyecto, Entrada.proyecto_id == Proyecto.id).join(Empresa, Entrada.empresa_id == Empresa.id)
            .where(Entrada.anulado.is_(False)).group_by(*columnas, Entrada.moneda))
    stmt = _periodo(stmt, Entrada.fecha, desde, hasta)
    if empresa_id:
        stmt = stmt.where(Entrada.empresa_id == empresa_id)
    if proyecto_id:
        stmt = stmt.where(Entrada.proyecto_id == proyecto_id)
    filas = []
    for fila in db.execute(stmt):
        *g, moneda, cantidad, total = fila
        filas.append({**({str(agrupar): g[0]} if g else {}), "moneda": moneda, "entradas": cantidad, "total": Decimal(total)})
    clave = agrupar if grupo is not None else "moneda"
    return sorted(filas, key=lambda f: (str(f.get(clave, "")).lower(), f["moneda"]))


def gastos(db: Session, *, agrupar: AgruparGastos, desde: date | None = None, hasta: date | None = None,
           empresa_id: uuid.UUID | None = None, proyecto_id: uuid.UUID | None = None) -> Reporte:
    """Gastos = porcentajes aplicados en las entradas. Por proyecto, por empresa o acumulados (por moneda)."""
    filas = _agrupado(db, Entrada.monto_gasto, agrupar=agrupar, desde=desde, hasta=hasta, empresa_id=empresa_id,
                      proyecto_id=proyecto_id)
    titulo = {AgruparGastos.PROYECTO: "Gastos por proyecto", AgruparGastos.EMPRESA: "Gastos por empresa",
              AgruparGastos.MONEDA: "Gastos acumulados"}[agrupar]
    columnas = ([(agrupar.value, agrupar.value.capitalize())] if agrupar != AgruparGastos.MONEDA else [])
    columnas += [("moneda", "Moneda"), ("entradas", "Entradas"), ("total", "Gastos")]
    totales = [] if agrupar == AgruparGastos.MONEDA else _totales_por_moneda(filas, ("total",), agrupar.value)
    return Reporte(titulo=titulo, columnas=columnas, filas=filas, totales=totales,
                   parametros=_parametros(desde, hasta, Empresa=_nombre(db, Empresa, empresa_id),
                                          Proyecto=_nombre(db, Proyecto, proyecto_id)))


def ingresos(db: Session, *, agrupar: AgruparIngresos, desde: date | None = None, hasta: date | None = None,
             empresa_id: uuid.UUID | None = None, proyecto_id: uuid.UUID | None = None) -> Reporte:
    """Ingresos = neto de las entradas (lo que llegó a las cuentas)."""
    filas = _agrupado(db, Entrada.monto_neto, agrupar=agrupar, desde=desde, hasta=hasta, empresa_id=empresa_id,
                      proyecto_id=proyecto_id)
    titulo = "Ingresos por proyecto" if agrupar == AgruparIngresos.PROYECTO else "Ingresos por empresa"
    return Reporte(
        titulo=titulo,
        columnas=[(agrupar.value, agrupar.value.capitalize()), ("moneda", "Moneda"), ("entradas", "Entradas"),
                  ("total", "Ingresos (neto)")],
        filas=filas,
        totales=_totales_por_moneda(filas, ("total",), agrupar.value),
        parametros=_parametros(desde, hasta, Empresa=_nombre(db, Empresa, empresa_id),
                               Proyecto=_nombre(db, Proyecto, proyecto_id)),
    )


# ------------------------------------------------------------------ inicio
def resumen(db: Session) -> dict[str, Any]:
    """Para la pantalla de inicio: dinero disponible por moneda (cajas, bancos, total)."""
    cuentas = db.execute(select(Cuenta.id, Cuenta.moneda, Cuenta.tipo)).all()
    saldos = saldos_cuentas(db)
    por_moneda: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"cajas": CERO, "bancos": CERO})
    for cid, moneda, tipo in cuentas:
        por_moneda[moneda]["cajas" if tipo == TipoCuenta.CAJA else "bancos"] += saldos[cid]
    return {
        "dinero": [{"moneda": m, **v, "total": v["cajas"] + v["bancos"]} for m, v in sorted(por_moneda.items())],
        "empresas": db.scalar(select(func.count()).select_from(Empresa).where(Empresa.activa.is_(True))),
        "proyectos": db.scalar(select(func.count()).select_from(Proyecto).where(Proyecto.activo.is_(True))),
    }
