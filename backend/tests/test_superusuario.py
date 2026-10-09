import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.errors import ReglaNegocio
from app.core.security import hash_password, verify_password
from app.db.session import SessionLocal
from app.models import AccionBitacora, Bitacora, Rol, Usuario
from app.services.usuarios import asegurar_superusuario


def _asegurar(password: str = "Super123", correo: str = "su@test.com", restablecer: bool = False) -> str:
    with SessionLocal() as db:
        return asegurar_superusuario(db, correo=correo, password=password, nombre="Súper", restablecer=restablecer)


def _superusuario() -> Usuario:
    with SessionLocal() as db:
        return db.scalar(select(Usuario).where(Usuario.rol == Rol.SUPERUSUARIO))


def test_se_crea_si_no_existe_y_queda_en_bitacora():
    assert "creado" in _asegurar()
    su = _superusuario()
    assert su.correo == "su@test.com" and verify_password("Super123", su.password_hash)
    with SessionLocal() as db:
        registro = db.scalar(select(Bitacora).where(Bitacora.entidad_id == su.id))
    assert registro.accion == AccionBitacora.CREAR and registro.usuario_id is None


def test_es_idempotente():
    _asegurar()
    assert "ya existe" in _asegurar(password="Distinta1")
    assert verify_password("Super123", _superusuario().password_hash)


def test_restablecer_asigna_la_password_y_el_correo_del_entorno():
    _asegurar()
    assert "restablecido" in _asegurar(password="Nueva123", correo="nuevo@test.com", restablecer=True)
    su = _superusuario()
    assert su.correo == "nuevo@test.com" and verify_password("Nueva123", su.password_hash)


@pytest.mark.parametrize("password", ["Corta1", "sololetras", "12345678"])
def test_password_invalida(password):
    with pytest.raises(ReglaNegocio):
        _asegurar(password=password)


def test_la_base_solo_admite_un_superusuario():
    _asegurar()
    with SessionLocal() as db:
        db.add(Usuario(nombre="Otro", correo="otro@test.com", password_hash=hash_password("x"), rol=Rol.SUPERUSUARIO))
        with pytest.raises(IntegrityError):
            db.commit()
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).where(Usuario.rol == Rol.SUPERUSUARIO)) == 1


def test_puede_iniciar_sesion(client):
    _asegurar()
    r = client.post("/auth/login", data={"username": "su@test.com", "password": "Super123"})
    assert r.status_code == 200
