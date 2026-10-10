import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func, text
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.models.usuario import Usuario


class Registrado:
    """Quién creó el registro y cuándo. Un contador solo puede corregir lo que él registró."""

    creado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"), index=True)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @declared_attr
    def autor(cls) -> Mapped[Usuario]:
        return relationship(Usuario, lazy="joined", foreign_keys=lambda: [cls.creado_por])

    @property
    def creado_por_nombre(self) -> str:
        return self.autor.nombre


class Anulable:
    """Los movimientos no se borran: se anulan con motivo y dejan de contar en los saldos."""

    anulado: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    motivo_anulacion: Mapped[str | None] = mapped_column(String(500))
    anulado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"))
    fecha_anulacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
