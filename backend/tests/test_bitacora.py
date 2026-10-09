import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db.session import SessionLocal
from tests.conftest import PASSWORD


def _bitacora(client, h, **filtros):
    r = client.get("/bitacora", params=filtros, headers=h)
    assert r.status_code == 200
    return r.json()["items"]


def test_registra_quien_hizo_cada_cosa(client, superusuario, admin):
    client.post("/usuarios", json={"nombre": "Ana", "correo": "ana@test.com", "password": "Clave123"},
                headers=admin[1])
    items = _bitacora(client, superusuario[1], usuario_id=str(admin[0].id))
    assert [(i["accion"], i["entidad"], i["usuario_nombre"]) for i in items] == [("CREAR", "Usuario", "Admin")]
    assert items[0]["detalle"]["despues"]["correo"] == "ana@test.com"


def test_registra_inicios_de_sesion_correctos_y_fallidos(client, admin, juan):
    client.post("/auth/login", data={"username": "juan@test.com", "password": PASSWORD})
    client.post("/auth/login", data={"username": "juan@test.com", "password": "mala1234"})
    acciones = [i["accion"] for i in _bitacora(client, admin[1], usuario_id=str(juan[0].id))]
    assert sorted(acciones) == ["INICIO_SESION", "INICIO_SESION_FALLIDO"]


def test_filtro_por_accion_y_fechas(client, admin, juan):
    client.post("/auth/login", data={"username": "juan@test.com", "password": PASSWORD})
    assert len(_bitacora(client, admin[1], accion="INICIO_SESION")) == 1
    assert _bitacora(client, admin[1], desde="2000-01-01", hasta="2000-01-31") == []
    r = client.get("/bitacora", params={"desde": "2026-02-01", "hasta": "2026-01-01"}, headers=admin[1])
    assert r.status_code == 422


def test_solo_admins_consultan_la_bitacora(client, juan):
    assert client.get("/bitacora", headers=juan[1]).status_code == 403


@pytest.mark.parametrize("sql", ["UPDATE bitacora SET entidad = 'x'", "DELETE FROM bitacora"])
def test_es_inmutable(client, juan, sql):
    client.post("/auth/login", data={"username": "juan@test.com", "password": PASSWORD})
    with SessionLocal() as db, pytest.raises(DBAPIError, match="no se puede modificar"):
        db.execute(text(sql))
