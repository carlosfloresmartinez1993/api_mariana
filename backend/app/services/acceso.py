"""Regla de acceso del sistema.

Todos los usuarios ven todo y pueden capturar. Corregir (editar, anular, cambiar el saldo inicial,
activar o desactivar) solo lo puede hacer quien registró el dato, o un administrador / superusuario.
La bitácora registra quién hizo cada cosa.
"""

import uuid
from typing import TypeVar

from sqlalchemy.orm import Session

from app.core.errors import NoEncontrado, Prohibido
from app.db.base import Base
from app.models import Usuario
from app.models.comun import Registrado

M = TypeVar("M", bound=Base)


def obtener(db: Session, modelo: type[M], id_: uuid.UUID, nombre: str, *, bloquear: bool = False) -> M:
    """Busca por id o responde 404 con «<nombre> no encontrado(a)». Con `bloquear`, SELECT … FOR UPDATE."""
    registro = db.get(modelo, id_, with_for_update=bloquear)
    if registro is None:
        raise NoEncontrado(f"{nombre} no encontrado" if nombre.endswith("o") else f"{nombre} no encontrada")
    return registro


def verificar_autor(usuario: Usuario, registro: Registrado) -> None:
    if not usuario.es_admin and registro.creado_por != usuario.id:
        raise Prohibido(f"Solo puedes corregir lo que tú registraste (esto lo registró {registro.creado_por_nombre})")
