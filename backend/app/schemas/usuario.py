import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.models.enums import Rol
from app.schemas.comun import ORMModel, Password

Correo = Annotated[EmailStr, AfterValidator(lambda v: v.strip().lower())]
Nombre = Annotated[str, Field(min_length=1, max_length=150)]
# El superusuario solo se crea desde las variables de entorno, nunca por la API.
RolAsignable = Literal[Rol.ADMIN, Rol.CONTADOR]


class UsuarioCrear(BaseModel):
    nombre: Nombre
    correo: Correo
    password: Password
    rol: RolAsignable = Rol.CONTADOR


class UsuarioActualizar(BaseModel):
    nombre: Nombre | None = None
    correo: Correo | None = None
    rol: RolAsignable | None = None


class RestablecerPassword(BaseModel):
    nueva: Password


class UsuarioOut(ORMModel):
    id: uuid.UUID
    nombre: str
    correo: str
    rol: Rol
    activo: bool
    fecha_creacion: datetime
