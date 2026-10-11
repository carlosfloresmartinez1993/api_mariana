"""Cálculo de saldos. Nada se guarda: todo sale de los movimientos vigentes (no anulados).

Cuenta:            entradas.monto_neto − salidas.monto  (no hay saldo inicial: todo entra por un proyecto)
Proyecto:          por empresa y moneda, ingresos (entradas.monto_neto) − salidas; gastos = entradas.monto_gasto.
                   Puede quedar en negativo (lo cubre el dinero de otros proyectos en la misma cuenta).
Cuadre (siempre):  por empresa y moneda,  Σ saldo de las cuentas = Σ saldos de los proyectos.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, func, select, union_all
from sqlalchemy.orm import Session

from app.core.errors import ReglaNegocio
from app.models import Cuenta, Entrada, Moneda, Proyecto, Salida

CERO = Decimal("0.00")


def _periodo(stmt: Select, columna, desde: date | None, hasta: date | None) -> Select:
    if desde:
        stmt = stmt.where(columna >= desde)
    if hasta:
        stmt = stmt.where(columna <= hasta)
    return stmt


def flujos_cuentas(desde: date | None = None, hasta: date | None = None):
    """Subconsulta (cuenta_id, monto) con cada movimiento vigente que afecta a una cuenta, con su signo."""
    partes = [
        _periodo(select(Entrada.cuenta_id.label("cuenta_id"), Entrada.monto_neto.label("monto"))
                 .where(Entrada.anulado.is_(False)), Entrada.fecha, desde, hasta),
        _periodo(select(Salida.cuenta_id, -Salida.monto).where(Salida.anulado.is_(False)), Salida.fecha, desde, hasta),
    ]
    return union_all(*partes).subquery("flujos")


def saldos_cuentas(db: Session, cuenta_ids: list[uuid.UUID] | None = None,
                   hasta: date | None = None) -> dict[uuid.UUID, Decimal]:
    """Saldo de cada cuenta (al día `hasta` si se indica). Incluye las cuentas sin movimientos."""
    flujos = flujos_cuentas(hasta=hasta)
    movido = select(flujos.c.cuenta_id, func.sum(flujos.c.monto).label("total")).group_by(flujos.c.cuenta_id)
    if cuenta_ids is not None:
        movido = movido.where(flujos.c.cuenta_id.in_(cuenta_ids))
    movido = movido.subquery()
    stmt = select(Cuenta.id, func.coalesce(movido.c.total, 0)).outerjoin(
        movido, movido.c.cuenta_id == Cuenta.id)
    if cuenta_ids is not None:
        stmt = stmt.where(Cuenta.id.in_(cuenta_ids))
    return {cid: Decimal(saldo) + CERO for cid, saldo in db.execute(stmt)}  # siempre con 2 decimales


@dataclass
class TotalesProyecto:
    ingresos: Decimal = CERO  # neto de las entradas
    gastos: Decimal = CERO  # porcentajes de las entradas
    salidas: Decimal = CERO

    @property
    def saldo(self) -> Decimal:
        return self.ingresos - self.salidas

    def __add__(self, otro: "TotalesProyecto") -> "TotalesProyecto":
        return TotalesProyecto(self.ingresos + otro.ingresos, self.gastos + otro.gastos, self.salidas + otro.salidas)


Clave = tuple[uuid.UUID, uuid.UUID, Moneda]  # (proyecto, empresa, moneda)


def totales_por_empresa(db: Session, proyecto_ids: list[uuid.UUID] | None = None, *,
                        empresa_id: uuid.UUID | None = None, desde: date | None = None,
                        hasta: date | None = None) -> dict[Clave, TotalesProyecto]:
    """Ingresos, gastos y salidas por (proyecto, empresa, moneda). Solo las combinaciones con movimientos."""
    entradas = _periodo(
        select(Entrada.proyecto_id, Entrada.empresa_id, Entrada.moneda, func.sum(Entrada.monto_neto),
               func.sum(Entrada.monto_gasto))
        .where(Entrada.anulado.is_(False)).group_by(Entrada.proyecto_id, Entrada.empresa_id, Entrada.moneda),
        Entrada.fecha, desde, hasta)
    salidas = _periodo(
        select(Salida.proyecto_id, Salida.empresa_id, Salida.moneda, func.sum(Salida.monto))
        .where(Salida.anulado.is_(False)).group_by(Salida.proyecto_id, Salida.empresa_id, Salida.moneda),
        Salida.fecha, desde, hasta)
    if proyecto_ids is not None:
        entradas = entradas.where(Entrada.proyecto_id.in_(proyecto_ids))
        salidas = salidas.where(Salida.proyecto_id.in_(proyecto_ids))
    if empresa_id:
        entradas = entradas.where(Entrada.empresa_id == empresa_id)
        salidas = salidas.where(Salida.empresa_id == empresa_id)

    totales: dict[Clave, TotalesProyecto] = defaultdict(TotalesProyecto)
    for pid, eid, moneda, neto, gasto in db.execute(entradas):
        t = totales[(pid, eid, Moneda(moneda))]
        t.ingresos, t.gastos = Decimal(neto), Decimal(gasto)
    for pid, eid, moneda, monto in db.execute(salidas):
        totales[(pid, eid, Moneda(moneda))].salidas = Decimal(monto)
    return dict(totales)


def totales_proyectos(db: Session, proyecto_ids: list[uuid.UUID] | None = None, *,
                      empresa_id: uuid.UUID | None = None, desde: date | None = None,
                      hasta: date | None = None) -> dict[tuple[uuid.UUID, Moneda], TotalesProyecto]:
    """Lo mismo, sumando todas las empresas: por (proyecto, moneda)."""
    totales: dict[tuple[uuid.UUID, Moneda], TotalesProyecto] = defaultdict(TotalesProyecto)
    for (pid, _, moneda), t in totales_por_empresa(db, proyecto_ids, empresa_id=empresa_id, desde=desde,
                                                   hasta=hasta).items():
        totales[(pid, moneda)] += t
    return dict(totales)


# ------------------------------------------------------------------ validación de saldos
def bloquear(db: Session, *, proyecto_ids: set[uuid.UUID] = frozenset(), cuenta_ids: set[uuid.UUID] = frozenset()) -> None:
    """SELECT … FOR UPDATE sobre los proyectos y cuentas afectados, siempre en el mismo orden.

    Así dos operaciones simultáneas sobre la misma cuenta o proyecto se esperan una a la otra
    y la validación de saldo no se puede saltar.
    """
    if proyecto_ids:
        db.execute(select(Proyecto.id).where(Proyecto.id.in_(proyecto_ids)).order_by(Proyecto.id).with_for_update())
    if cuenta_ids:
        db.execute(select(Cuenta.id).where(Cuenta.id.in_(cuenta_ids)).order_by(Cuenta.id).with_for_update())


def validar_no_negativos(db: Session, *, cuenta_ids: set[uuid.UUID]) -> None:
    """Después de aplicar un cambio (ya con flush): ninguna cuenta puede quedar en negativo.

    Los proyectos sí pueden: un proyecto con pérdida se paga con el dinero de otros que está en la cuenta.
    """
    db.flush()
    if cuenta_ids:
        for cid, saldo in saldos_cuentas(db, list(cuenta_ids)).items():
            if saldo < 0:
                cuenta = db.get(Cuenta, cid)
                raise ReglaNegocio(
                    f"Saldo insuficiente: la cuenta «{cuenta.nombre}» de {cuenta.empresa.nombre} "
                    f"quedaría en {saldo:,.2f} {cuenta.moneda}"
                )


# ------------------------------------------------------------------ cuadre
@dataclass
class Cuadre:
    entradas: Decimal = CERO  # neto
    salidas: Decimal = CERO
    saldo_cuentas: Decimal = CERO
    saldo_proyectos: Decimal = CERO

    @property
    def diferencia(self) -> Decimal:
        """Siempre 0: lo que hay en las cuentas es exactamente el saldo de los proyectos."""
        return self.saldo_cuentas - self.saldo_proyectos


def cuadre(db: Session, *, hasta: date | None = None, empresa_id: uuid.UUID | None = None
           ) -> dict[tuple[uuid.UUID, Moneda], Cuadre]:
    """Por (empresa, moneda): entradas, salidas, saldo de las cuentas y saldo de los proyectos."""
    stmt = select(Cuenta.id, Cuenta.empresa_id, Cuenta.moneda)
    if empresa_id:
        stmt = stmt.where(Cuenta.empresa_id == empresa_id)
    cuentas = db.execute(stmt).all()
    saldos = saldos_cuentas(db, [c.id for c in cuentas], hasta=hasta)
    resultado: dict[tuple[uuid.UUID, Moneda], Cuadre] = defaultdict(Cuadre)
    for c in cuentas:
        resultado[(c.empresa_id, Moneda(c.moneda))].saldo_cuentas += saldos[c.id]
    for (_, eid, moneda), t in totales_por_empresa(db, empresa_id=empresa_id, hasta=hasta).items():
        r = resultado[(eid, moneda)]
        r.entradas += t.ingresos
        r.salidas += t.salidas
        r.saldo_proyectos += t.saldo
    return dict(resultado)
