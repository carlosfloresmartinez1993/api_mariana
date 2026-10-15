"""Carga masiva de entradas y salidas de un proyecto desde Excel (FECHA, CONCEPTO, CARGO, ABONO)."""

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile

from app.api.deps import DB, UsuarioActual
from app.core.config import settings
from app.core.errors import ReglaNegocio
from app.models import Proyecto
from app.services import carga_masiva
from app.services.acceso import obtener
from app.services.serializacion import a_json

router = APIRouter(tags=["Carga masiva"])

CHUNK = 64 * 1024
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def _contenido(archivo: UploadFile) -> bytes:
    limite = settings.MAX_DOCUMENTO_MB * 1024 * 1024 * 2
    datos = bytearray()
    while bloque := await archivo.read(CHUNK):
        datos += bloque
        if len(datos) > limite:
            raise ReglaNegocio(f"El archivo excede el máximo de {settings.MAX_DOCUMENTO_MB * 2} MB")
    return bytes(datos)


def _opciones(
    empresa_id: Annotated[uuid.UUID, Form()],
    cuenta_entradas_id: Annotated[uuid.UUID, Form()],
    cuenta_salidas_id: Annotated[uuid.UUID, Form()],
    porcentaje_gasto: Annotated[Decimal, Form(ge=0, le=100, decimal_places=2)] = Decimal("0"),
    categoria_entradas_id: Annotated[uuid.UUID | None, Form()] = None,
    categoria_salidas_id: Annotated[uuid.UUID | None, Form()] = None,
    requiere_factura_entradas: Annotated[bool, Form()] = False,
    requiere_factura_salidas: Annotated[bool, Form()] = False,
) -> carga_masiva.Opciones:
    return carga_masiva.Opciones(
        empresa_id=empresa_id, cuenta_entradas_id=cuenta_entradas_id, cuenta_salidas_id=cuenta_salidas_id,
        porcentaje_gasto=porcentaje_gasto, categoria_entradas_id=categoria_entradas_id,
        categoria_salidas_id=categoria_salidas_id, requiere_factura_entradas=requiere_factura_entradas,
        requiere_factura_salidas=requiere_factura_salidas)


Opciones = Annotated[carga_masiva.Opciones, Depends(_opciones)]
Archivo = Annotated[UploadFile, File(description="Excel con las columnas FECHA, CONCEPTO, CARGO y ABONO")]


@router.get("/carga-masiva/plantilla", response_class=Response, summary="Excel de ejemplo para la carga masiva")
def plantilla(_: UsuarioActual):
    return Response(carga_masiva.plantilla(), media_type=XLSX,
                    headers={"Content-Disposition": 'attachment; filename="plantilla-carga-masiva.xlsx"'})


@router.post("/proyectos/{proyecto_id}/carga-masiva/vista-previa", summary="Revisar el Excel sin registrar nada")
async def vista_previa(proyecto_id: uuid.UUID, db: DB, _: UsuarioActual, archivo: Archivo, op: Opciones):
    proyecto = obtener(db, Proyecto, proyecto_id, "Proyecto")
    return a_json(carga_masiva.vista_previa(db, proyecto, await _contenido(archivo), op))


@router.post("/proyectos/{proyecto_id}/carga-masiva", summary="Registrar las entradas y después las salidas del Excel")
async def cargar(proyecto_id: uuid.UUID, db: DB, usuario: UsuarioActual, archivo: Archivo, op: Opciones):
    """Todo o nada: si alguna fila tiene error, o alguna cuenta quedaría en negativo, no se registra nada."""
    proyecto = obtener(db, Proyecto, proyecto_id, "Proyecto")
    return carga_masiva.cargar(db, proyecto, await _contenido(archivo), archivo.filename, op, usuario)
