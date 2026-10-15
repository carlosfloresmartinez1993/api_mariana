import uuid

from pydantic import BaseModel, Field

from app.schemas.comun import Nombre100, TextoOpcional
from app.schemas.empresa import Registro


class CategoriaCrear(BaseModel):
    nombre: Nombre100
    descripcion: TextoOpcional = Field(default=None, max_length=255)


class CategoriaActualizar(BaseModel):
    nombre: Nombre100 | None = None
    descripcion: TextoOpcional = Field(default=None, max_length=255)


class CategoriaOut(Registro):
    id: uuid.UUID
    nombre: str
    descripcion: str | None
    activa: bool
