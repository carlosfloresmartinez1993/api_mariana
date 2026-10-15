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

from app.core.tiempo import hoy

from app.models import (
    Categoria,
    Cuenta,
    Empresa,
    EmpresaProyecto,
    Entrada,
    Moneda,
    Pendiente,
    Proyecto,
    Salida,
    TipoCuenta,
    TipoPendiente,
)
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
        if not f.get("moneda"):  # p. ej. un proyecto sin movimientos
            continue
        for c in columnas:
            suma[f["moneda"]][c] += f.get(c) or 0
    return [{etiqueta: f"TOTAL {m}", "moneda": m, **valores} for m, valores in sorted(suma.items())]


# ------------------------------------------------------------------ proyectos
def saldos_proyectos(db: Session, *, desde: date | None = None, hasta: date | None = None,
                     empresa_id: uuid.UUID | None = None, proyecto_id: uuid.UUID | None = None,
                     por_empresa: bool = False) -> Reporte:
    """Todos los proyectos, tengan movimientos o no (con empresa: los vinculados a ella).

    Con `por_empresa`, una fila por proyecto, empresa y moneda: el dinero que el proyecto tiene en cada empresa.
    Un saldo negativo significa que el proyecto usó dinero de otros proyectos.
    """
    consulta = select(Proyecto.id, Proyecto.nombre)
    if proyecto_id:
        consulta = consulta.where(Proyecto.id == proyecto_id)
    if empresa_id:
        consulta = consulta.where(Proyecto.id.in_(select(EmpresaProyecto.proyecto_id)
                                                  .where(EmpresaProyecto.empresa_id == empresa_id)))
    proyectos = dict(db.execute(consulta).all())
    totales = totales_por_empresa(db, list(proyectos), empresa_id=empresa_id, desde=desde, hasta=hasta)
    empresas = dict(db.execute(select(Empresa.id, Empresa.nombre).where(Empresa.id.in_({e for _, e, _ in totales}))).all())
    agrupados: dict[tuple, TotalesProyecto] = defaultdict(TotalesProyecto)
    for (pid, eid, m), t in totales.items():
        agrupados[(pid, empresas[eid] if por_empresa else None, m)] += t
    con_movimientos = {pid for pid, _, _ in agrupados}
    filas = [{"proyecto": proyectos[pid], **({"empresa": e} if por_empresa else {}), "moneda": m,
              "ingresos": t.ingresos, "gastos": t.gastos, "salidas": t.salidas, "saldo": t.saldo}
             for (pid, e, m), t in agrupados.items()]
    filas += [{"proyecto": nombre, **({"empresa": None} if por_empresa else {}), "moneda": None, "ingresos": CERO,
               "gastos": CERO, "salidas": CERO, "saldo": CERO}
              for pid, nombre in proyectos.items() if pid not in con_movimientos]
    filas.sort(key=lambda f: (f["proyecto"].lower(), (f.get("empresa") or "").lower(), f["moneda"] or ""))
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
    """Resumen de ingresos y egresos del proyecto: una fila por entrada (neto) y por salida, una columna por
    moneda, totales y resultado neto. Con `desde`, empieza con el saldo anterior.

    Cada fila lleva `estilo` (seccion, ingreso, egreso, total, resultado, saldo) para darle formato.
    """
    entradas = select(Entrada).where(Entrada.proyecto_id == proyecto.id, Entrada.anulado.is_(False))
    salidas = select(Salida).where(Salida.proyecto_id == proyecto.id, Salida.anulado.is_(False))
    if empresa_id:
        entradas = entradas.where(Entrada.empresa_id == empresa_id)
        salidas = salidas.where(Salida.empresa_id == empresa_id)
    lista_entradas = sorted(db.scalars(_periodo(entradas, Entrada.fecha, desde, hasta)).unique(),
                            key=lambda m: (m.fecha, m.fecha_creacion))
    lista_salidas = sorted(db.scalars(_periodo(salidas, Salida.fecha, desde, hasta)).unique(),
                           key=lambda m: (m.fecha, m.fecha_creacion))
    anteriores = (totales_proyectos(db, [proyecto.id], empresa_id=empresa_id, hasta=desde - timedelta(days=1))
                  if desde else {})
    saldo_anterior = {m: t.saldo for (_, m), t in anteriores.items()}

    usadas = {m.moneda for m in lista_entradas + lista_salidas} | set(saldo_anterior)
    monedas = [m for m in (Moneda.MXN, Moneda.USD) if m in usadas] or [Moneda.MXN]

    def detalle(mov) -> str:
        return f"{mov.fecha:%d/%m/%Y} · {mov.empresa.nombre} · {mov.cuenta.nombre}"

    def fila(estilo: str, concepto: str, montos: dict, detalle_: str | None = None) -> dict[str, Any]:
        return {"estilo": estilo, "concepto": concepto, "detalle": detalle_, **{m.value: montos.get(m) for m in monedas}}

    filas: list[dict[str, Any]] = []
    if desde:
        filas.append(fila("saldo", f"SALDO ANTERIOR AL {desde:%d/%m/%Y}", {m: saldo_anterior.get(m, CERO) for m in monedas}))

    ingresos: dict[Moneda, Decimal] = defaultdict(lambda: CERO)
    filas.append(fila("seccion", "INGRESOS", {}))
    for e in lista_entradas:
        concepto = e.concepto or e.referencia or "Entrada"
        if e.porcentaje_gasto:
            concepto += f" (bruto {e.monto:,.2f}, gasto {e.porcentaje_gasto:.2f} %)"
        filas.append(fila("ingreso", concepto, {e.moneda: e.monto_neto}, detalle(e)))
        ingresos[e.moneda] += e.monto_neto
    filas.append(fila("total", "TOTAL INGRESOS", {m: ingresos[m] for m in monedas}))

    egresos: dict[Moneda, Decimal] = defaultdict(lambda: CERO)
    filas.append(fila("seccion", "EGRESOS", {}))
    for s in lista_salidas:
        concepto = f"{s.concepto} — {s.beneficiario}" if s.beneficiario else s.concepto
        filas.append(fila("egreso", concepto, {s.moneda: s.monto}, detalle(s)))
        egresos[s.moneda] += s.monto
    filas.append(fila("total", "TOTAL EGRESOS", {m: egresos[m] for m in monedas}))

    filas.append(fila("resultado", "RESULTADO NETO DEL PROYECTO",
                      {m: saldo_anterior.get(m, CERO) + ingresos[m] - egresos[m] for m in monedas}))
    return Reporte(
        titulo=f"Resumen de ingresos y egresos — {proyecto.nombre}",
        columnas=[("concepto", "Concepto"), *[(m.value, m.value) for m in monedas]],
        filas=filas,
        parametros=_parametros(desde, hasta, Proyecto=proyecto.nombre, Empresa=_nombre(db, Empresa, empresa_id)),
        estilo="resumen",
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


# ------------------------------------------------------------------ categorías
SIN_CATEGORIA = "Sin categoría"


def por_categoria(db: Session, *, desde: date | None = None, hasta: date | None = None,
                  empresa_id: uuid.UUID | None = None, proyecto_id: uuid.UUID | None = None,
                  por_proyecto: bool = False) -> Reporte:
    """Entradas (neto) y salidas por categoría y moneda. Con `por_proyecto`, una fila por proyecto y categoría."""
    filas_por: dict[tuple, dict[str, Any]] = {}

    def acumular(modelo, columna_monto, clave_monto: str) -> None:
        columnas = [Categoria.nombre, modelo.moneda] + ([Proyecto.nombre] if por_proyecto else [])
        stmt = (select(*columnas, func.count(), func.sum(columna_monto))
                .select_from(modelo).outerjoin(Categoria, modelo.categoria_id == Categoria.id)
                .join(Proyecto, modelo.proyecto_id == Proyecto.id)
                .where(modelo.anulado.is_(False)).group_by(*columnas))
        stmt = _periodo(stmt, modelo.fecha, desde, hasta)
        if empresa_id:
            stmt = stmt.where(modelo.empresa_id == empresa_id)
        if proyecto_id:
            stmt = stmt.where(modelo.proyecto_id == proyecto_id)
        for fila in db.execute(stmt):
            categoria, moneda, *resto = fila
            proyecto = resto[0] if por_proyecto else None
            cantidad, total = resto[-2], resto[-1]
            clave = (proyecto, categoria or SIN_CATEGORIA, moneda)
            f = filas_por.setdefault(clave, {**({"proyecto": proyecto} if por_proyecto else {}),
                                             "categoria": categoria or SIN_CATEGORIA, "moneda": moneda,
                                             "movimientos": 0, "entradas": CERO, "salidas": CERO})
            f["movimientos"] += cantidad
            f[clave_monto] += Decimal(total)

    acumular(Entrada, Entrada.monto_neto, "entradas")
    acumular(Salida, Salida.monto, "salidas")
    filas = list(filas_por.values())
    for f in filas:
        f["neto"] = f["entradas"] - f["salidas"]
    filas.sort(key=lambda f: ((f.get("proyecto") or "").lower(), f["categoria"] == SIN_CATEGORIA,
                              f["categoria"].lower(), f["moneda"]))
    return Reporte(
        titulo="Por proyecto y categoría" if por_proyecto else "Por categoría",
        columnas=[*([("proyecto", "Proyecto")] if por_proyecto else []), ("categoria", "Categoría"),
                  ("moneda", "Moneda"), ("movimientos", "Movimientos"), ("entradas", "Entradas (neto)"),
                  ("salidas", "Salidas"), ("neto", "Neto")],
        filas=filas,
        totales=_totales_por_moneda(filas, ("entradas", "salidas", "neto"),
                                    "proyecto" if por_proyecto else "categoria"),
        parametros=_parametros(desde, hasta, Empresa=_nombre(db, Empresa, empresa_id),
                               Proyecto=_nombre(db, Proyecto, proyecto_id)),
    )


# ------------------------------------------------------------------ proyecciones
def _porcentaje(real: Decimal, estimado: Decimal | None) -> Decimal | None:
    if not estimado:
        return None
    return (real * 100 / estimado).quantize(Decimal("0.01"))


def estimado_vs_real(db: Session, *, proyecto_id: uuid.UUID | None = None,
                     solo_con_estimados: bool = False) -> Reporte:
    """Por proyecto y moneda: ingresos y gastos (salidas) estimados contra los reales, avance en %,
    cuentas por cobrar y por pagar pendientes. Las proyecciones no afectan ningún saldo."""
    consulta = select(Proyecto).order_by(Proyecto.nombre)
    if proyecto_id:
        consulta = consulta.where(Proyecto.id == proyecto_id)
    proyectos = list(db.scalars(consulta).unique())
    reales = totales_proyectos(db, [p.id for p in proyectos]) if proyectos else {}
    pendientes: dict[tuple, Decimal] = defaultdict(lambda: CERO)
    if proyectos:
        for pid, tipo, moneda, total in db.execute(
                select(Pendiente.proyecto_id, Pendiente.tipo, Pendiente.moneda, func.sum(Pendiente.monto))
                .where(Pendiente.liquidada.is_(False), Pendiente.proyecto_id.in_([p.id for p in proyectos]))
                .group_by(Pendiente.proyecto_id, Pendiente.tipo, Pendiente.moneda)):
            pendientes[(pid, TipoPendiente(tipo), Moneda(moneda))] = Decimal(total)

    filas = []
    for p in proyectos:
        for moneda in (Moneda.MXN, Moneda.USD):
            sufijo = moneda.value.lower()
            est_ing = getattr(p, f"estimado_ingresos_{sufijo}")
            est_gas = getattr(p, f"estimado_gastos_{sufijo}")
            real = reales.get((p.id, moneda))
            cobrar = pendientes[(p.id, TipoPendiente.POR_COBRAR, moneda)]
            pagar = pendientes[(p.id, TipoPendiente.POR_PAGAR, moneda)]
            hay_estimado = est_ing is not None or est_gas is not None
            if not (hay_estimado or real or cobrar or pagar) or (solo_con_estimados and not hay_estimado):
                continue
            ingresos = real.ingresos if real else CERO
            salidas = real.salidas if real else CERO
            filas.append({
                "proyecto": p.nombre, "moneda": moneda,
                "ingresos_estimados": est_ing, "ingresos_reales": ingresos, "avance_ingresos": _porcentaje(ingresos, est_ing),
                "gastos_estimados": est_gas, "gastos_reales": salidas, "avance_gastos": _porcentaje(salidas, est_gas),
                "resultado_estimado": (est_ing or CERO) - (est_gas or CERO) if hay_estimado else None,
                "resultado_real": ingresos - salidas,
                "por_cobrar": cobrar, "por_pagar": pagar,
                "trabajadores": p.trabajadores_estimados if moneda == Moneda.MXN else None,
                "inicio_estimado": p.fecha_inicio_estimada if moneda == Moneda.MXN else None,
                "fin_estimado": p.fecha_fin_estimada if moneda == Moneda.MXN else None,
            })
    return Reporte(
        titulo="Estimado contra real",
        columnas=[("proyecto", "Proyecto"), ("moneda", "Moneda"), ("ingresos_estimados", "Ingresos estimados"),
                  ("ingresos_reales", "Ingresos reales (neto)"), ("avance_ingresos", "% ingresos"),
                  ("gastos_estimados", "Gastos estimados"), ("gastos_reales", "Salidas reales"),
                  ("avance_gastos", "% gastos"), ("resultado_estimado", "Resultado estimado"),
                  ("resultado_real", "Resultado real"), ("por_cobrar", "Por cobrar"), ("por_pagar", "Por pagar"),
                  ("trabajadores", "Trabajadores est."), ("inicio_estimado", "Inicio est."),
                  ("fin_estimado", "Fin est.")],
        filas=filas,
        totales=_totales_por_moneda(filas, ("ingresos_estimados", "ingresos_reales", "gastos_estimados",
                                            "gastos_reales", "resultado_estimado", "resultado_real",
                                            "por_cobrar", "por_pagar"), "proyecto"),
        parametros={**({"Proyecto": proyectos[0].nombre} if proyecto_id and proyectos else {})},
    )


# ------------------------------------------------------------------ cuentas por cobrar y por pagar
def cuentas_por_cobrar_pagar(db: Session, *, proyecto_id: uuid.UUID | None = None,
                             incluir_liquidadas: bool = False) -> Reporte:
    """Una fila por partida; el monto va en la columna «Por cobrar» o «Por pagar». Totales por moneda."""
    stmt = select(Pendiente).join(Pendiente.proyecto).order_by(
        Proyecto.nombre, Pendiente.fecha_vencimiento.asc().nulls_last(), Pendiente.concepto)
    if proyecto_id:
        stmt = stmt.where(Pendiente.proyecto_id == proyecto_id)
    if not incluir_liquidadas:
        stmt = stmt.where(Pendiente.liquidada.is_(False))
    hoy_ = hoy()
    filas = []
    for p in db.scalars(stmt).unique():
        cobrar = p.tipo == TipoPendiente.POR_COBRAR
        if p.liquidada:
            estado = "Liquidada"
        elif p.fecha_vencimiento and p.fecha_vencimiento < hoy_:
            estado = "VENCIDA"
        else:
            estado = "Pendiente"
        filas.append({"proyecto": p.proyecto.nombre, "concepto": p.concepto, "contraparte": p.contraparte,
                      "moneda": p.moneda, "por_cobrar": p.monto if cobrar else None,
                      "por_pagar": None if cobrar else p.monto, "vencimiento": p.fecha_vencimiento,
                      "estado": estado})
    totales = _totales_por_moneda(filas, ("por_cobrar", "por_pagar"), "proyecto")
    for t in totales:
        t["diferencia"] = t["por_cobrar"] - t["por_pagar"]
    return Reporte(
        titulo="Cuentas por cobrar y por pagar",
        columnas=[("proyecto", "Proyecto"), ("concepto", "Concepto"), ("contraparte", "Cliente / proveedor"),
                  ("moneda", "Moneda"), ("por_cobrar", "Por cobrar"), ("por_pagar", "Por pagar"),
                  ("diferencia", "Diferencia"), ("vencimiento", "Vencimiento"), ("estado", "Estado")],
        filas=filas,
        totales=totales,
        parametros={"Incluye liquidadas": "sí" if incluir_liquidadas else "no",
                    **({"Proyecto": _nombre(db, Proyecto, proyecto_id)} if proyecto_id else {})},
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
