import uuid
from datetime import datetime

from sqlalchemy import (
    DDL,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPk
from app.models.comun import Registrado
from app.models.enums import Moneda, TipoCuenta, enum_columna


class Empresa(UUIDPk, Registrado, Base):
    __tablename__ = "empresas"
    __table_args__ = (Index("uq_empresas_nombre", func.lower(text("nombre")), unique=True),)

    nombre: Mapped[str] = mapped_column(String(200))
    activa: Mapped[bool] = mapped_column(default=True, server_default=true())

    cuentas: Mapped[list["Cuenta"]] = relationship(back_populates="empresa", order_by="Cuenta.nombre")


class Proyecto(UUIDPk, Registrado, Base):
    __tablename__ = "proyectos"
    __table_args__ = (Index("uq_proyectos_nombre", func.lower(text("nombre")), unique=True),)

    nombre: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str | None] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(default=True, server_default=true())

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
