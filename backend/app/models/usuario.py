from datetime import datetime

from sqlalchemy import DateTime, Index, String, func, text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPk
from app.models.enums import Rol, enum_columna


class Usuario(UUIDPk, Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        # Solo puede existir un superusuario.
        Index("uq_usuarios_superusuario", "rol", unique=True, postgresql_where=text("rol = 'superusuario'")),
    )

    nombre: Mapped[str] = mapped_column(String(150))
    correo: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    rol: Mapped[Rol] = mapped_column(enum_columna(Rol, "rol_usuario", 20))
    activo: Mapped[bool] = mapped_column(default=True, server_default=true())
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def es_superusuario(self) -> bool:
        return self.rol == Rol.SUPERUSUARIO

    @property
    def es_admin(self) -> bool:
        """Administrador o superusuario: ven y modifican todo."""
        return self.rol in (Rol.ADMIN, Rol.SUPERUSUARIO)
