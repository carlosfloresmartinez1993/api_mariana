from sqlalchemy import func, select

from app import seed
from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Empresa, Rol, Usuario
from tests.conftest import crear_usuario


def _contar(modelo) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(modelo))


def test_nunca_en_produccion(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert seed.main() == 1
    assert _contar(Usuario) == 0 and _contar(Empresa) == 0


def test_no_carga_si_ya_hay_usuarios_aunque_no_haya_empresas():
    crear_usuario("real@empresa.com", Rol.ADMIN)
    assert seed.main() == 1
    assert _contar(Usuario) == 1 and _contar(Empresa) == 0


def test_carga_en_base_vacia_aunque_exista_el_superusuario():
    crear_usuario("su@empresa.com", Rol.SUPERUSUARIO)
    assert seed.main() == 0
    assert _contar(Empresa) > 0
