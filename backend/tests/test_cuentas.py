import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db.session import SessionLocal
from tests.helpers import crear_cuenta, crear_empresa, crear_proyecto, entrada, ok, salida


@pytest.fixture
def empresa(client, juan):
    return crear_empresa(client, juan[1])


def test_varias_cuentas_de_banco_y_una_caja_por_moneda(client, juan, empresa):
    h = juan[1]
    crear_cuenta(client, h, empresa["id"], "banco", "MXN", banco="BBVA")
    crear_cuenta(client, h, empresa["id"], "banco", "MXN", nombre="Santander nómina")
    crear_cuenta(client, h, empresa["id"], "banco", "USD", banco="BBVA")
    caja = crear_cuenta(client, h, empresa["id"], "caja", "MXN")
    assert caja["nombre"] == "Caja MXN"
    r = client.post("/cuentas", json={"empresa_id": empresa["id"], "tipo": "caja", "moneda": "MXN",
                                      "nombre": "Otra caja"}, headers=h)
    assert r.status_code == 409
    crear_cuenta(client, h, empresa["id"], "caja", "USD")
    assert len(ok(client.get("/cuentas", params={"empresa_id": empresa["id"]}, headers=h))) == 5


def test_cuenta_nueva_empieza_en_cero(client, juan, empresa):
    cuenta = crear_cuenta(client, juan[1], empresa["id"])
    assert cuenta["saldo"] == "0.00" and "saldo_inicial" not in cuenta
    # Ya no existe el saldo inicial: el dinero que había se registra como una entrada de un proyecto.
    r = client.post(f"/cuentas/{cuenta['id']}/saldo-inicial", json={"saldo_inicial": "1", "motivo": "x"},
                    headers=juan[1])
    assert r.status_code in (404, 405)


def test_la_moneda_no_cambia(client, juan, empresa):
    cuenta = crear_cuenta(client, juan[1], empresa["id"], "banco", "MXN")
    editada = ok(client.patch(f"/cuentas/{cuenta['id']}", json={"moneda": "USD", "nombre": "Principal"},
                              headers=juan[1]))
    assert editada["moneda"] == "MXN" and editada["nombre"] == "Principal"
    with SessionLocal() as db, pytest.raises(DBAPIError, match="no se pueden cambiar"):
        db.execute(text("UPDATE cuentas SET moneda = 'USD' WHERE id = :id"), {"id": cuenta["id"]})


def test_desactivar_solo_con_saldo_en_cero(client, juan, empresa):
    h = juan[1]
    cuenta = crear_cuenta(client, h, empresa["id"])
    proyecto = crear_proyecto(client, h)
    entrada(client, h, proyecto, cuenta, "10")
    assert client.post(f"/cuentas/{cuenta['id']}/desactivar", headers=h).status_code == 422
    salida(client, h, proyecto, cuenta, "10")
    assert ok(client.post(f"/cuentas/{cuenta['id']}/desactivar", headers=h))["activa"] is False
    entrada(client, h, proyecto, cuenta, "100", esperado=422)


def test_otro_contador_no_corrige_la_cuenta(client, juan, pedro, empresa):
    cuenta = crear_cuenta(client, juan[1], empresa["id"])
    assert client.patch(f"/cuentas/{cuenta['id']}", json={"nombre": "X"}, headers=pedro[1]).status_code == 403
    assert client.post(f"/cuentas/{cuenta['id']}/desactivar", headers=pedro[1]).status_code == 403


def test_empresa_desactivada_no_recibe_cuentas(client, juan, empresa):
    ok(client.post(f"/empresas/{empresa['id']}/desactivar", headers=juan[1]))
    r = client.post("/cuentas", json={"empresa_id": empresa["id"], "tipo": "banco", "moneda": "MXN"}, headers=juan[1])
    assert r.status_code == 422
