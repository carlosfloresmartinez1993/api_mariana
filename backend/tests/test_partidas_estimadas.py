import pytest

from tests.helpers import crear_cuenta, crear_empresa, crear_proyecto, entrada, ok, salida


@pytest.fixture
def base(client, juan):
    h = juan[1]
    empresa = crear_empresa(client, h)
    cat = {n: ok(client.post("/categorias", json={"nombre": n}, headers=h), 201)
           for n in ("Materiales", "Mano de obra", "Anticipos")}
    return {"h": h, "banco": crear_cuenta(client, h, empresa["id"]), "cat": cat}


def _partida(client, h, proyecto, tipo, monto, moneda="MXN", categoria=None, concepto=None, esperado=201):
    datos = {"tipo": tipo, "moneda": moneda, "monto": monto, "concepto": concepto,
             "categoria_id": categoria["id"] if categoria else None}
    return ok(client.post(f"/proyectos/{proyecto['id']}/partidas-estimadas", json=datos, headers=h), esperado)


def _proyecto(client, h, proyecto):
    return ok(client.get(f"/proyectos/{proyecto['id']}", headers=h))


def test_alta_con_partidas_calcula_totales(client, base):
    h, cat = base["h"], base["cat"]
    p = crear_proyecto(client, h, estimado_ingresos_mxn="1", partidas=[
        {"tipo": "ingreso", "categoria_id": cat["Anticipos"]["id"], "moneda": "MXN", "monto": "500000"},
        {"tipo": "gasto", "categoria_id": cat["Materiales"]["id"], "concepto": "Cemento", "moneda": "MXN",
         "monto": "200000"},
        {"tipo": "gasto", "categoria_id": cat["Materiales"]["id"], "concepto": "Varilla", "moneda": "MXN",
         "monto": "50000.50"},
        {"tipo": "gasto", "moneda": "USD", "monto": "1000"},
    ])
    # Con partidas, los totales son la suma (el estimado manual se ignora).
    assert p["num_partidas_estimadas"] == 4
    assert (p["estimado_ingresos_mxn"], p["estimado_gastos_mxn"]) == ("500000.00", "250000.50")
    assert (p["estimado_ingresos_usd"], p["estimado_gastos_usd"]) == (None, "1000.00")
    partidas = ok(client.get(f"/proyectos/{p['id']}/partidas-estimadas", headers=h))
    assert [x["tipo"] for x in partidas] == ["ingreso", "gasto", "gasto", "gasto"]
    assert partidas[1]["categoria_nombre"] == "Materiales"


def test_editar_y_eliminar_recalcula(client, base):
    h, cat = base["h"], base["cat"]
    p = crear_proyecto(client, h, estimado_gastos_mxn="999")
    assert _proyecto(client, h, p)["estimado_gastos_mxn"] == "999.00"  # sin partidas: manual
    a = _partida(client, h, p, "gasto", "100", categoria=cat["Materiales"])
    b = _partida(client, h, p, "gasto", "50", categoria=cat["Mano de obra"])
    assert _proyecto(client, h, p)["estimado_gastos_mxn"] == "150.00"
    ok(client.patch(f"/partidas-estimadas/{a['id']}", json={"monto": "300", "tipo": "ingreso"}, headers=h))
    datos = _proyecto(client, h, p)
    assert (datos["estimado_ingresos_mxn"], datos["estimado_gastos_mxn"]) == ("300.00", "50.00")
    r = client.delete(f"/partidas-estimadas/{b['id']}", headers=h)
    assert r.status_code == 204
    assert _proyecto(client, h, p)["estimado_gastos_mxn"] is None
    # Con partidas, los totales no se editan a mano (pero mandar el mismo valor no falla).
    assert client.patch(f"/proyectos/{p['id']}", json={"estimado_ingresos_mxn": "1"}, headers=h).status_code == 422
    ok(client.patch(f"/proyectos/{p['id']}", json={"nombre": "Otro", "estimado_ingresos_mxn": "300"}, headers=h))


def test_validaciones(client, base, pedro):
    h, cat = base["h"], base["cat"]
    p = crear_proyecto(client, h)
    _partida(client, h, p, "gasto", "0", esperado=422)
    _partida(client, h, p, "otro", "10", esperado=422)
    ok(client.post(f"/categorias/{cat['Anticipos']['id']}/desactivar", headers=h))
    _partida(client, h, p, "ingreso", "10", categoria=cat["Anticipos"], esperado=422)
    a = _partida(client, h, p, "gasto", "10")
    # Otro contador no corrige partidas ajenas.
    assert client.patch(f"/partidas-estimadas/{a['id']}", json={"monto": "1"}, headers=pedro[1]).status_code == 403
    assert client.delete(f"/partidas-estimadas/{a['id']}", headers=pedro[1]).status_code == 403


def test_reporte_estimado_contra_real_por_categoria(client, base):
    h, cat, b = base["h"], base["cat"], base["banco"]
    p = crear_proyecto(client, h, partidas=[
        {"tipo": "ingreso", "categoria_id": cat["Anticipos"]["id"], "moneda": "MXN", "monto": "1000"},
        {"tipo": "gasto", "categoria_id": cat["Materiales"]["id"], "moneda": "MXN", "monto": "400"},
    ])
    crear_proyecto(client, h, "Sin partidas")  # no aparece
    entrada(client, h, p, b, "800", "10", categoria_id=cat["Anticipos"]["id"])  # neto 720
    salida(client, h, p, b, "500", categoria_id=cat["Materiales"]["id"])
    salida(client, h, p, b, "20")  # sin categoría
    reporte = ok(client.get("/reportes/estimado-vs-real", params={"por_categoria": True}, headers=h))
    filas = {f["categoria"]: f for f in reporte["filas"]}
    assert list(filas) == ["Anticipos", "Materiales", "Sin categoría"]
    assert {f["proyecto"] for f in reporte["filas"]} == {p["nombre"]}
    assert (filas["Anticipos"]["ingresos_estimados"], filas["Anticipos"]["ingresos_reales"]) == ("1000.00", "720.00")
    assert filas["Anticipos"]["diferencia_ingresos"] == "-280.00"
    assert filas["Materiales"]["avance_gastos"] == "125.00"
    assert filas["Materiales"]["disponible_gastos"] == "-100.00"
    assert filas["Sin categoría"]["gastos_estimados"] is None and filas["Sin categoría"]["gastos_reales"] == "20.00"
    assert reporte["totales"][0]["disponible_gastos"] == "-120.00"
    for formato in ("xlsx", "pdf", "csv"):
        r = client.get("/reportes/estimado-vs-real", params={"por_categoria": True, "formato": formato}, headers=h)
        assert r.status_code == 200, r.text


def test_seed_con_partidas_estimadas(client, admin):
    from app import seed

    assert seed.main() == 0
    torre = next(p for p in ok(client.get("/proyectos", params={"q": "Torre"}, headers=admin[1]))["items"])
    assert torre["num_partidas_estimadas"] == 7
    assert (torre["estimado_ingresos_mxn"], torre["estimado_gastos_mxn"]) == ("1500000.00", "900000.00")
    assert (torre["estimado_ingresos_usd"], torre["estimado_gastos_usd"]) == ("25000.00", "15000.00")
