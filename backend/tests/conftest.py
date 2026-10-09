import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url


def _url_de_pruebas() -> str:
    """BD de pruebas: TEST_DATABASE_URL si está definida; si no, la del .env con el sufijo _test.

    Con DATABASE_URL=postgresql+psycopg://postgres:clave@localhost:5432/empresas
    las pruebas usan .../empresas_test, con el mismo usuario y contraseña.
    """
    if url := os.environ.get("TEST_DATABASE_URL"):
        return url
    base = os.environ.get("DATABASE_URL") or dotenv_values(Path(__file__).parents[1] / ".env").get("DATABASE_URL")
    if not base:
        raise RuntimeError("Define DATABASE_URL en el .env o TEST_DATABASE_URL")
    url = make_url(base)
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


URL_PRUEBAS = _url_de_pruebas()
NOMBRE_BD = make_url(URL_PRUEBAS).database or ""
# Las pruebas BORRAN todo el esquema. Protección contra apuntar por error a la base real.
if not NOMBRE_BD.endswith("_test") and os.environ.get("PRUEBAS_EN_BD_REAL") != "si":
    raise SystemExit(
        f"Las pruebas borran todos los datos de la base «{NOMBRE_BD}». "
        "Usa una base terminada en _test, o define PRUEBAS_EN_BD_REAL=si si realmente quieres borrarla."
    )

# La configuración se lee al importar la app: definir el entorno de pruebas antes.
os.environ["DATABASE_URL"] = URL_PRUEBAS
os.environ["SECRET_KEY"] = "pruebas-" + "x" * 40
os.environ["ENVIRONMENT"] = "test"
os.environ["RATE_LIMIT_ENABLED"] = "false"
# Sin superusuario automático: cada prueba crea los usuarios que necesita.
os.environ["SUPERUSUARIO_CORREO"] = ""
os.environ["SUPERUSUARIO_PASSWORD"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import Rol, Usuario

PASSWORD = "Secreta123"


@pytest.fixture(scope="session", autouse=True)
def esquema():
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    Base.metadata.create_all(engine)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def limpiar():
    yield
    tablas = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    with engine.begin() as conn:
        # TRUNCATE no dispara los triggers de fila, así que también limpia la bitácora.
        conn.execute(text(f"TRUNCATE {tablas} CASCADE"))


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def crear_usuario(correo: str, rol: Rol, nombre: str = "Nombre") -> Usuario:
    with SessionLocal() as db:
        usuario = Usuario(nombre=nombre, correo=correo, password_hash=hash_password(PASSWORD), rol=rol)
        db.add(usuario)
        db.commit()
        return usuario


def headers(usuario: Usuario) -> dict[str, str]:
    token, _ = create_access_token(usuario.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def superusuario():
    u = crear_usuario("super@test.com", Rol.SUPERUSUARIO, "Súper")
    return u, headers(u)


@pytest.fixture
def admin():
    u = crear_usuario("admin@test.com", Rol.ADMIN, "Admin")
    return u, headers(u)


@pytest.fixture
def juan():
    u = crear_usuario("juan@test.com", Rol.CONTADOR, "Juan")
    return u, headers(u)


@pytest.fixture
def pedro():
    u = crear_usuario("pedro@test.com", Rol.CONTADOR, "Pedro")
    return u, headers(u)
