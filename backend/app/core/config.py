from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración leída de variables de entorno (o del archivo .env)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Control de Empresas y Proyectos"
    ENVIRONMENT: Literal["development", "production", "test"] = "development"

    # Base de datos (PostgreSQL con driver psycopg 3)
    DATABASE_URL: str = Field(examples=["postgresql+psycopg://usuario:password@localhost:5432/empresas"])

    @field_validator("DATABASE_URL")
    @classmethod
    def _driver_psycopg(cls, valor: str) -> str:
        # Render, Railway y otros entregan postgres:// o postgresql://; SQLAlchemy necesita el driver.
        for prefijo in ("postgres://", "postgresql://"):
            if valor.startswith(prefijo):
                return "postgresql+psycopg://" + valor[len(prefijo):]
        return valor

    # Seguridad
    SECRET_KEY: str = Field(min_length=32, description="Clave para firmar los JWT; generar con `openssl rand -hex 32`")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=5, le=24 * 60)
    CORS_ORIGINS: list[str] = []
    LOGIN_RATE_LIMIT: str = "5/minute"
    RATE_LIMIT_ENABLED: bool = True
    DOCS_ENABLED: bool = True

    # Zona horaria del negocio: define qué es "hoy" y los límites de los periodos
    TIMEZONE: str = "America/Tijuana"

    # Build del frontend (frontend/dist) que sirve app.servidor en producción
    FRONTEND_DIR: Path = Path("./static")

    # Superusuario: se crea al arrancar la API si no existe (en cualquier servidor).
    # Con SUPERUSUARIO_RESTABLECER=true se le vuelve a asignar la contraseña del entorno en cada arranque.
    SUPERUSUARIO_CORREO: str | None = None
    SUPERUSUARIO_PASSWORD: SecretStr | None = None
    SUPERUSUARIO_NOMBRE: str = "Superusuario"
    SUPERUSUARIO_RESTABLECER: bool = False

    @field_validator("SUPERUSUARIO_CORREO", "SUPERUSUARIO_PASSWORD", mode="before")
    @classmethod
    def _vacio_es_nulo(cls, valor: object) -> object:
        # strip(): en los paneles de Render/Railway es fácil pegar un espacio o salto de línea al final.
        if isinstance(valor, str):
            valor = valor.strip()
            return valor or None
        return valor


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
