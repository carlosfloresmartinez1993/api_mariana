import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DDL, DateTime, ForeignKey, Index, String, event, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPk
from app.models.enums import AccionBitacora, enum_columna
from app.models.usuario import Usuario


class Bitacora(UUIDPk, Base):
    __tablename__ = "bitacora"
    __table_args__ = (
        Index("ix_bitacora_entidad", "entidad", "entidad_id"),
        Index("ix_bitacora_fecha", "fecha"),
    )

    # NULL cuando la acción la ejecuta el sistema (p. ej. crear el superusuario al arrancar).
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"), index=True)
    entidad: Mapped[str] = mapped_column(String(50))
    entidad_id: Mapped[uuid.UUID | None]
    accion: Mapped[AccionBitacora] = mapped_column(enum_columna(AccionBitacora, "accion_bitacora", 40))
    detalle: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    usuario: Mapped[Usuario | None] = relationship(lazy="joined")

    @property
    def usuario_nombre(self) -> str:
        return self.usuario.nombre if self.usuario else "Sistema"


# La bitácora es de solo inserción: la BD rechaza UPDATE y DELETE sobre ella.
# (La migración inicial crea lo mismo; esto cubre create_all en pruebas.)
BITACORA_INMUTABLE_SQL = """
CREATE OR REPLACE FUNCTION bitacora_inmutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'La bitácora no se puede modificar ni borrar';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_bitacora_inmutable
    BEFORE UPDATE OR DELETE ON bitacora
    FOR EACH ROW EXECUTE FUNCTION bitacora_inmutable();
"""

event.listen(Bitacora.__table__, "after_create", DDL(BITACORA_INMUTABLE_SQL))
