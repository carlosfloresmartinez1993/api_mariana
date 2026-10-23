import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    DDL,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    select,
    text,
    true,
)
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from app.db.base import Base, UUIDPk
from app.models.comun import Registrado
from app.models.enums import Moneda, TipoCuenta, TipoEstimado, TipoPendiente, enum_columna


class Empresa(UUIDPk, Registrado, Base):
    __tablename__ = "empresas"
    __table_args__ = (Index("uq_empresas_nombre", func.lower(text("nombre")), unique=True),)

    nombre: Mapped[str] = mapped_column(String(200))
    activa: Mapped[bool] = mapped_column(default=True, server_default=true())

    cuentas: Mapped[list["Cuenta"]] = relationship(back_populates="empresa", order_by="Cuenta.nombre")


class Proyecto(UUIDPk, Registrado, Base):
    """Las proyecciones (estimados) son opcionales y no afectan ningún saldo: sirven para comparar con lo real."""

    __tablename__ = "proyectos"
    __table_args__ = (
        Index("uq_proyectos_nombre", func.lower(text("nombre")), unique=True),
        CheckConstraint("estimado_ingresos_mxn >= 0 AND estimado_gastos_mxn >= 0 AND estimado_ingresos_usd >= 0 "
                        "AND estimado_gastos_usd >= 0 AND trabajadores_estimados >= 0", name="estimados_no_negativos"),
        CheckConstraint("fecha_fin_estimada >= fecha_inicio_estimada", name="fechas_estimadas"),
    )

    nombre: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str | None] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(default=True, server_default=true())

    # Proyecciones (opcionales)
    estimado_ingresos_mxn: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    estimado_gastos_mxn: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    estimado_ingresos_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    estimado_gastos_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    trabajadores_estimados: Mapped[int | None]
    fecha_inicio_estimada: Mapped[date | None] = mapped_column(Date)
    fecha_fin_estimada: Mapped[date | None] = mapped_column(Date)

    empresas: Mapped[list[Empresa]] = relationship(secondary="empresa_proyecto", order_by=Empresa.nombre,
                                                   viewonly=True)


class EmpresaProyecto(Base):
    """Un proyecto puede estar en varias empresas. Se crea solo al registrar una entrada o salida."""

    __tablename__ = "empresa_proyecto"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id", ondelete="RESTRICT"), primary_key=True)
    proyecto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proyectos.id", ondelete="RESTRICT"), primary_key=True,
                                                   index=True)
    creado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"))
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Cuenta(UUIDPk, Registrado, Base):
    """Cuenta de banco o caja de efectivo de una empresa. La moneda no cambia nunca.

    No tiene saldo inicial: todo el dinero entra por una entrada de un proyecto, así las cuentas siempre
    cuadran con los proyectos. El dinero que ya había se registra como una entrada (p. ej. «Saldo de apertura»).
    """

    __tablename__ = "cuentas"
    __table_args__ = (
        # Una sola caja por moneda en cada empresa.
        Index("uq_cuentas_caja_por_moneda", "empresa_id", "moneda", unique=True,
              postgresql_where=text("tipo = 'caja'")),
        Index("uq_cuentas_nombre", "empresa_id", func.lower(text("nombre")), unique=True),
        # Destino de las llaves foráneas compuestas de entradas y salidas:
        # garantizan que la cuenta sea de esa empresa y de esa moneda.
        UniqueConstraint("id", "empresa_id", "moneda", name="uq_cuentas_id_empresa_moneda"),
    )

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id", ondelete="RESTRICT"), index=True)
    tipo: Mapped[TipoCuenta] = mapped_column(enum_columna(TipoCuenta, "tipo_cuenta", 10))
    moneda: Mapped[Moneda] = mapped_column(enum_columna(Moneda, "moneda", 3))
    nombre: Mapped[str] = mapped_column(String(100))
    banco: Mapped[str | None] = mapped_column(String(100))
    numero: Mapped[str | None] = mapped_column(String(30))
    activa: Mapped[bool] = mapped_column(default=True, server_default=true())

    empresa: Mapped[Empresa] = relationship(back_populates="cuentas", lazy="joined", innerjoin=True)

    @property
    def empresa_nombre(self) -> str:
        return self.empresa.nombre


# La empresa, el tipo y la moneda de una cuenta no se pueden cambiar (la API tampoco lo permite).
# (La migración crea lo mismo; esto cubre create_all en pruebas.)
CUENTA_INMUTABLE_SQL = """
CREATE OR REPLACE FUNCTION cuenta_inmutable() RETURNS trigger AS $$
BEGIN
    IF NEW.moneda <> OLD.moneda OR NEW.tipo <> OLD.tipo OR NEW.empresa_id <> OLD.empresa_id THEN
        RAISE EXCEPTION 'La empresa, el tipo y la moneda de una cuenta no se pueden cambiar';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_cuenta_inmutable
    BEFORE UPDATE ON cuentas
    FOR EACH ROW EXECUTE FUNCTION cuenta_inmutable();
"""

event.listen(Cuenta.__table__, "after_create", DDL(CUENTA_INMUTABLE_SQL))


class Categoria(UUIDPk, Registrado, Base):
    """Categoría opcional de entradas y salidas (una sola lista para ambas)."""

    __tablename__ = "categorias"
    __table_args__ = (Index("uq_categorias_nombre", func.lower(text("nombre")), unique=True),)

    nombre: Mapped[str] = mapped_column(String(100))
    descripcion: Mapped[str | None] = mapped_column(String(255))
    activa: Mapped[bool] = mapped_column(default=True, server_default=true())


class PartidaEstimada(UUIDPk, Registrado, Base):
    """Ingreso o gasto estimado de un proyecto, por categoría y moneda. No afecta saldos.

    Si el proyecto tiene partidas, sus totales estimados (estimado_ingresos_mxn, …) son la suma de ellas.
    """

    __tablename__ = "partidas_estimadas"
    __table_args__ = (
        CheckConstraint("monto > 0", name="monto_positivo"),
        Index("ix_partidas_estimadas_proyecto_tipo", "proyecto_id", "tipo"),
    )

    proyecto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proyectos.id", ondelete="RESTRICT"))
    tipo: Mapped[TipoEstimado] = mapped_column(enum_columna(TipoEstimado, "tipo_estimado", 7))
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categorias.id", ondelete="RESTRICT"),
                                                           index=True)
    concepto: Mapped[str | None] = mapped_column(String(255))
    moneda: Mapped[Moneda] = mapped_column(enum_columna(Moneda, "moneda", 3))
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    proyecto: Mapped[Proyecto] = relationship(lazy="joined", innerjoin=True)
    categoria: Mapped[Categoria | None] = relationship(lazy="joined")

    @property
    def categoria_nombre(self) -> str | None:
        return self.categoria.nombre if self.categoria else None


Proyecto.num_partidas_estimadas = column_property(
    select(func.count(PartidaEstimada.id)).where(PartidaEstimada.proyecto_id == Proyecto.id)
    .correlate_except(PartidaEstimada).scalar_subquery())


class Pendiente(UUIDPk, Registrado, Base):
    """Cuenta por cobrar o por pagar de un proyecto. No afecta saldos: al cobrar o pagar se registra la entrada
    o salida como siempre y la partida se marca como liquidada."""

    __tablename__ = "pendientes"
    __table_args__ = (
        CheckConstraint("monto > 0", name="monto_positivo"),
        CheckConstraint("liquidada OR fecha_liquidacion IS NULL", name="liquidacion_coherente"),
        Index("ix_pendientes_proyecto_tipo", "proyecto_id", "tipo"),
    )

    proyecto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proyectos.id", ondelete="RESTRICT"))
    tipo: Mapped[TipoPendiente] = mapped_column(enum_columna(TipoPendiente, "tipo_pendiente", 12))
    concepto: Mapped[str] = mapped_column(String(255))
    contraparte: Mapped[str | None] = mapped_column(String(200))  # cliente o proveedor
    moneda: Mapped[Moneda] = mapped_column(enum_columna(Moneda, "moneda", 3))
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date)
    liquidada: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    fecha_liquidacion: Mapped[date | None] = mapped_column(Date)
    nota: Mapped[str | None] = mapped_column(Text)

    proyecto: Mapped[Proyecto] = relationship(lazy="joined", innerjoin=True)

    @property
    def proyecto_nombre(self) -> str:
        return self.proyecto.nombre
