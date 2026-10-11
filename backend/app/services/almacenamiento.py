"""Dónde se guardan los archivos (facturas). La BD solo guarda la clave (ruta relativa).

Mismo uso en local y en línea; ALMACENAMIENTO elige el destino:
  local → carpeta ARCHIVOS_DIR
  s3    → bucket compatible con S3 (Railway Buckets, Supabase Storage, Cloudflare R2, AWS S3)
"""
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.core.config import settings
from app.core.errors import NoEncontrado


class Almacenamiento(Protocol):
    def guardar(self, clave: str, contenido: bytes, tipo: str) -> None: ...
    def leer(self, clave: str) -> bytes: ...
    def eliminar(self, clave: str) -> None: ...


class Local:
    def __init__(self, raiz: Path):
        self.raiz = raiz.resolve()

    def _ruta(self, clave: str) -> Path:
        ruta = (self.raiz / clave).resolve()
        if not ruta.is_relative_to(self.raiz):  # defensa ante path traversal
            raise NoEncontrado("Archivo no encontrado")
        return ruta

    def guardar(self, clave: str, contenido: bytes, tipo: str) -> None:
        ruta = self._ruta(clave)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_suffix(ruta.suffix + ".part")
        try:
            temporal.write_bytes(contenido)
            temporal.replace(ruta)  # nunca queda un archivo a medias
        finally:
            temporal.unlink(missing_ok=True)

    def leer(self, clave: str) -> bytes:
        ruta = self._ruta(clave)
        if not ruta.is_file():
            raise NoEncontrado("El archivo ya no está en el almacenamiento")
        return ruta.read_bytes()

    def eliminar(self, clave: str) -> None:
        self._ruta(clave).unlink(missing_ok=True)


class S3:
    def __init__(self):
        import boto3
        from botocore.config import Config

        self.bucket = settings.S3_BUCKET
        self.prefijo = settings.S3_PREFIJO
        self.cliente = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            region_name=settings.S3_REGION,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            # path-style: lo piden varios proveedores compatibles con S3
            config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3, "mode": "standard"}),
        )

    def guardar(self, clave: str, contenido: bytes, tipo: str) -> None:
        self.cliente.put_object(Bucket=self.bucket, Key=self.prefijo + clave, Body=contenido, ContentType=tipo)

    def leer(self, clave: str) -> bytes:
        try:
            return self.cliente.get_object(Bucket=self.bucket, Key=self.prefijo + clave)["Body"].read()
        except self.cliente.exceptions.NoSuchKey:
            raise NoEncontrado("El archivo ya no está en el almacenamiento") from None

    def eliminar(self, clave: str) -> None:
        self.cliente.delete_object(Bucket=self.bucket, Key=self.prefijo + clave)


@lru_cache
def almacenamiento() -> Almacenamiento:
    return S3() if settings.ALMACENAMIENTO == "s3" else Local(settings.ARCHIVOS_DIR)
