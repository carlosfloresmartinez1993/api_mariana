"""Factura de una entrada o salida (opcional): validación, nombre y clave en el almacenamiento.

Se aceptan PDF, XML (CFDI), JPG y PNG. El tipo se valida por el contenido del archivo, no por la extensión.
"""

import logging
import uuid
from pathlib import PurePath
from urllib.parse import quote

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import NoEncontrado, ReglaNegocio
from app.core.tiempo import ahora
from app.models import AccionBitacora, Entrada, Salida, Usuario
from app.services.acceso import verificar_autor
from app.services.almacenamiento import almacenamiento
from app.services.bitacora import registrar

log = logging.getLogger(__name__)
CHUNK = 64 * 1024

# (extensión, tipo MIME) según los primeros bytes del archivo
TIPOS = {"pdf": "application/pdf", "xml": "application/xml", "jpg": "image/jpeg", "png": "image/png"}


def detectar_tipo(contenido: bytes) -> str | None:
    if contenido.startswith(b"%PDF-"):
        return "pdf"
    if contenido.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if contenido.startswith(b"\xff\xd8\xff"):
        return "jpg"
    inicio = contenido[:200].lstrip(b"\xef\xbb\xbf \t\r\n")  # BOM y espacios
    if inicio.startswith(b"<?xml") or inicio.startswith(b"<cfdi:"):
        return "xml"
    return None


def nombre_limpio(original: str | None, extension: str) -> str:
    # Solo el nombre (sin la ruta del equipo del usuario) y sin caracteres de control.
    nombre = PurePath((original or "").replace("\\", "/")).name
    nombre = "".join(c for c in nombre if c.isprintable()).strip() or f"factura.{extension}"
    if not nombre.lower().endswith(f".{extension}") and not (extension == "jpg" and nombre.lower().endswith(".jpeg")):
        nombre += f".{extension}"
    return nombre[-255:]


async def leer(archivo: UploadFile) -> tuple[bytes, str]:
    """Lee el archivo con límite de tamaño. Devuelve (contenido, extensión)."""
    limite = settings.MAX_DOCUMENTO_MB * 1024 * 1024
    partes: list[bytes] = []
    leidos = 0
    while bloque := await archivo.read(CHUNK):
        leidos += len(bloque)
        if leidos > limite:
            raise ReglaNegocio(f"El archivo excede el máximo de {settings.MAX_DOCUMENTO_MB} MB")
        partes.append(bloque)
    contenido = b"".join(partes)
    if not contenido:
        raise ReglaNegocio("El archivo está vacío")
    extension = detectar_tipo(contenido)
    if extension is None:
        raise ReglaNegocio("La factura debe ser PDF, XML, JPG o PNG")
    return contenido, extension


def _borrar_sin_fallar(clave: str | None) -> None:
    """Borra un archivo que ya no usa ningún registro. Si falla, solo queda huérfano: se registra y sigue."""
    if not clave:
        return
    try:
        almacenamiento().eliminar(clave)
    except Exception:  # noqa: BLE001 - el cambio en la BD ya se confirmó
        log.exception("No se pudo borrar el archivo %s del almacenamiento", clave)


def _entidad(mov: Entrada | Salida) -> str:
    return "Entrada" if isinstance(mov, Entrada) else "Salida"


async def subir(db: Session, mov: Entrada | Salida, archivo: UploadFile, usuario: Usuario) -> Entrada | Salida:
    """Adjunta la factura; si ya tenía una, la reemplaza. Queda en la bitácora."""
    verificar_autor(usuario, mov)
    if mov.anulado:
        raise ReglaNegocio("No se puede adjuntar factura a un movimiento anulado")
    contenido, extension = await leer(archivo)
    nombre = nombre_limpio(archivo.filename, extension)
    anterior_clave, anterior_nombre = mov.factura_clave, mov.factura_nombre
    # Nombre aleatorio: no depende del nombre que puso el usuario y no choca al reemplazar.
    clave = f"{_entidad(mov).lower()}s/{mov.id}/{uuid.uuid4().hex}.{extension}"
    almacenamiento().guardar(clave, contenido, TIPOS[extension])
    try:
        mov.factura_clave, mov.factura_nombre = clave, nombre
        mov.factura_tipo, mov.factura_tamano, mov.factura_subida_en = TIPOS[extension], len(contenido), ahora()
        registrar(db, usuario_id=usuario.id, entidad=_entidad(mov), entidad_id=mov.id,
                  accion=AccionBitacora.SUBIR_FACTURA,
                  detalle={"nombre": nombre, "tamano": len(contenido), "reemplaza": anterior_nombre})
        db.commit()
    except Exception:
        db.rollback()
        _borrar_sin_fallar(clave)  # que no quede un archivo sin registro
        raise
    _borrar_sin_fallar(anterior_clave)
    db.refresh(mov)
    return mov


def quitar(db: Session, mov: Entrada | Salida, usuario: Usuario) -> Entrada | Salida:
    verificar_autor(usuario, mov)
    if not mov.factura_clave:
        raise NoEncontrado("El movimiento no tiene factura")
    clave, nombre = mov.factura_clave, mov.factura_nombre
    mov.factura_clave = mov.factura_nombre = mov.factura_tipo = None
    mov.factura_tamano = mov.factura_subida_en = None
    registrar(db, usuario_id=usuario.id, entidad=_entidad(mov), entidad_id=mov.id,
              accion=AccionBitacora.ELIMINAR_FACTURA, detalle={"nombre": nombre})
    db.commit()
    _borrar_sin_fallar(clave)
    db.refresh(mov)
    return mov


def contenido(mov: Entrada | Salida) -> tuple[bytes, str, str]:
    """(bytes, tipo MIME, Content-Disposition) para descargar o ver la factura."""
    if not mov.factura_clave:
        raise NoEncontrado("El movimiento no tiene factura")
    datos = almacenamiento().leer(mov.factura_clave)
    nombre = mov.factura_nombre or "factura"
    ascii_ = nombre.encode("ascii", "replace").decode().replace('"', "").replace("?", "_")
    return datos, mov.factura_tipo or "application/octet-stream", \
        f"inline; filename=\"{ascii_}\"; filename*=UTF-8''{quote(nombre)}"
