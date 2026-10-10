import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Computed, Date, ForeignKey, ForeignKeyConstraint, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPk
from app.models.comun import Anulable, Registrado
from app.models.empresa import Cuenta, Empresa, Proyecto
from app.models.enums import Forma, Moneda, enum_columna

GASTO_SQL = "round(monto * porcentaje_gasto / 100, 2)"


class Entrada(UUIDPk, Registrado, Anulable, Base):
    """Dinero que entra a un proyecto, en una cuenta de una empresa.

    El gasto (porcentaje) se lo queda el proveedor antes: a la cuenta llega el neto.
    """

    __tablename__ = "entradas"
    __table_args__ = (
        ForeignKeyConstraint(["empresa_id", "proyecto_id"],
                             ["empresa_proyecto.empresa_id", "empresa_proyecto.proyecto_id"],
                             name="fk_entradas_empresa_proyecto", ondelete="RESTRICT"),
        ForeignKeyConstraint(["cuenta_id", "empresa_id", "moneda"],
                             ["cuentas.id", "cuentas.empresa_id", "cuentas.moneda"],
                             name="fk_entradas_cuenta_empresa_moneda", ondelete="RESTRICT"),
        CheckConstraint("monto > 0", name="monto_positivo"),
        CheckConstraint("porcentaje_gasto >= 0 AND porcentaje_gasto < 100", name="porcentaje_valido"),
        Index("ix_entradas_proyecto_fecha", "proyecto_id", "fecha"),
        Index("ix_entradas_cuenta", "cuenta_id"),
        Index("ix_entradas_fecha", "fecha"),
    )

    proyecto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proyectos.id", ondelete="RESTRICT"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id", ondelete="RESTRICT"))
    cuenta_id: Mapped[uuid.UUID] = mapped_column()
    moneda: Mapped[Moneda] = mapped_column(enum_columna(Moneda, "moneda", 3))
    fecha: Mapped[date] = mapped_column(Date)
    forma: Mapped[Forma] = mapped_column(enum_columna(Forma, "forma", 15))
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    porcentaje_gasto: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), server_default=text("0"))
    monto_gasto: Mapped[Decimal] = mapped_column(Numeric(14, 2), Computed(GASTO_SQL, persisted=True))
    monto_neto: Mapped[Decimal] = mapped_column(Numeric(14, 2), Computed(f"monto - {GASTO_SQL}", persisted=True))
    concepto: Mapped[str | None] = mapped_column(String(255))
    referencia: Mapped[str | None] = mapped_column(String(100))

    proyecto: Mapped[Proyecto] = relationship(lazy="joined", innerjoin=True)
    empresa: Mapped[Empresa] = relationship(lazy="joined", innerjoin=True)
    cuenta: Mapped[Cuenta] = relationship(lazy="joined", innerjoin=True, foreign_keys=[cuenta_id],
                                          primaryjoin="Entrada.cuenta_id == Cuenta.id")

    @property
    def proyecto_nombre(self) -> str:
        return self.proyecto.nombre

    @property
    def empresa_nombre(self) -> str:
        return self.empresa.nombre

    @property
    def cuenta_nombre(self) -> str:
        return self.cuenta.nombre


class Salida(UUIDPk, Registrado, Anulable, Base):
    """Dinero que sale de un proyecto, desde una cuenta de una empresa."""

    __tablename__ = "salidas"
    __table_args__ = (
        ForeignKeyConstraint(["empresa_id", "proyecto_id"],
                             ["empresa_proyecto.empresa_id", "empresa_proyecto.proyecto_id"],
                             name="fk_salidas_empresa_proyecto", ondelete="RESTRICT"),
        ForeignKeyConstraint(["cuenta_id", "empresa_id", "moneda"],
                             ["cuentas.id", "cuentas.empresa_id", "cuentas.moneda"],
                             name="fk_salidas_cuenta_empresa_moneda", ondelete="RESTRICT"),
        CheckConstraint("monto > 0", name="monto_positivo"),
        Index("ix_salidas_proyecto_fecha", "proyecto_id", "fecha"),
        Index("ix_salidas_cuenta", "cuenta_id"),
        Index("ix_salidas_fecha", "fecha"),
    )

    proyecto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proyectos.id", ondelete="RESTRICT"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id", ondelete="RESTRICT"))
    cuenta_id: Mapped[uuid.UUID] = mapped_column()
    moneda: Mapped[Moneda] = mapped_column(enum_columna(Moneda, "moneda", 3))
    fecha: Mapped[date] = mapped_column(Date)
    forma: Mapped[Forma] = mapped_column(enum_columna(Forma, "forma", 15))
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    concepto: Mapped[str] = mapped_column(String(255))
    beneficiario: Mapped[str | None] = mapped_column(String(200))

    proyecto: Mapped[Proyecto] = relationship(lazy="joined", innerjoin=True)
    empresa: Mapped[Empresa] = relationship(lazy="joined", innerjoin=True)
    cuenta: Mapped[Cuenta] = relationship(lazy="joined", innerjoin=True, foreign_keys=[cuenta_id],
                                          primaryjoin="Salida.cuenta_id == Cuenta.id")

    @property
    def proyecto_nombre(self) -> str:
        return self.proyecto.nombre

    @property
    def empresa_nombre(self) -> str:
        return self.empresa.nombre

    @property
    def cuenta_nombre(self) -> str:
        return self.cuenta.nombre

