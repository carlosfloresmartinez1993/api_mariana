from typing import Any

from pydantic import BaseModel


class Columna(BaseModel):
    clave: str
    etiqueta: str


class ReporteOut(BaseModel):
    titulo: str
    parametros: dict[str, Any]
    columnas: list[Columna]
    filas: list[dict[str, Any]]
    totales: list[dict[str, Any]] = []
    elaborado_por: str | None = None
