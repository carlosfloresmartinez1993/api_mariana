import pytest

from tests.helpers import crear_cuenta, crear_empresa, crear_proyecto, entrada, ok, salida


@pytest.fixture
def base(client, juan):
    h = juan[1]
    empresa = crear_empresa(client, h)
    return {"h": h, "banco": crear_cuenta(client, h, empresa["id"]),
            "usd": crear_cuenta(client, h, empresa["id"], "banco", "USD"), "proyecto": crear_proyecto(client, h)}


def _categoria(client, h, nombre, esperado=201):
    return ok(client.post("/categorias", json={"nombre": nombre}, headers=h), esperado)


# ------------------------------------------------------------------ categorías
def test_categorias_opcionales_en_entradas_y_salidas(client, base):
    h, p, b = base["h"], base["proyecto"], base["banco"]
    materiales = _categoria(client, h, "Materiales")
    sin = entrada(client, h, p, b, "1000")
    assert sin["categoria_id"] is None and sin["categoria_nombre"] is None
    con = salida(client, h, p, b, "200", categoria_id=materiales["id"])
    assert con["categoria_nombre"] == "Materiales"
    editada = ok(client.patch(f"/entradas/{sin['id']}", json={"categoria_id": materiales["id"]}, headers=h))
    assert editada["categoria_nombre"] == "Materiales"
    quitada = ok(client.patch(f"/entradas/{sin['id']}", json={"categoria_id": None}, headers=h))
    assert quitada["categoria_id"] is None
    assert ok(client.get("/salidas", params={"categoria_id": materiales["id"]}, headers=h))["total"] == 1


def test_categoria_unica_y_desactivada_no_se_ofrece(client, base):
    h = base["h"]
    nomina = _categoria(client, h, "Nómina")
    _categoria(client, h, "NÓMINA", esperado=409)
    ok(client.post(f"/categorias/{nomina['id']}/desactivar", headers=h))
    assert [c["nombre"] for c in ok(client.get("/categorias", params={"activa": "true"}, headers=h))] == []
    salida(client, h, base["proyecto"], base["banco"], "1", categoria_id=nomina["id"], esperado=422)


def test_otro_contador_no_corrige_la_categoria(client, base, pedro):
    cat = _categoria(client, base["h"], "Renta")
    assert client.patch(f"/categorias/{cat['id']}", json={"nombre": "X"}, headers=pedro[1]).status_code == 403


def test_reporte_por_categoria(client, base):
    h, p, b = base["h"], base["proyecto"], base["banco"]
    materiales, nomina = _categoria(client, h, "Materiales"), _categoria(client, h, "Nómina")
    entrada(client, h, p, b, "10000", "3", categoria_id=materiales["id"])  # neto 9700
    salida(client, h, p, b, "2000", categoria_id=materiales["id"])
    salida(client, h, p, b, "500", categoria_id=nomina["id"])
    salida(client, h, p, b, "100")
    r = ok(client.get("/reportes/por-categoria", headers=h))
    filas = {f["categoria"]: (f["entradas"], f["salidas"], f["neto"]) for f in r["filas"]}
    assert filas == {"Materiales": ("9700.00", "2000.00", "7700.00"), "Nómina": ("0.00", "500.00", "-500.00"),
                     "Sin categoría": ("0.00", "100.00", "-100.00")}
    assert r["filas"][-1]["categoria"] == "Sin categoría"
    por_proyecto = ok(client.get("/reportes/por-categoria", params={"por_proyecto": "true"}, headers=h))
    assert {f["proyecto"] for f in por_proyecto["filas"]} == {"Torre Centro"}


# ------------------------------------------------------------------ proyecciones
def test_proyecciones_opcionales_que_no_afectan_saldos(client, base):
    h = base["h"]
    p = ok(client.post("/proyectos", json={
        "nombre": "Bodega", "estimado_ingresos_mxn": "1000000", "estimado_gastos_mxn": "800000",
        "trabajadores_estimados": 25, "fecha_inicio_estimada": "2026-11-01", "fecha_fin_estimada": "2027-03-31",
    }, headers=h), 201)
    assert (p["estimado_ingresos_mxn"], p["trabajadores_estimados"], p["fecha_fin_estimada"]) == \
        ("1000000.00", 25, "2027-03-31")
    assert p["saldos"] == []  # los estimados no son dinero
    editado = ok(client.patch(f"/proyectos/{p['id']}", json={"estimado_gastos_usd": "5000",
                                                            "trabajadores_estimados": None}, headers=h))
    assert (editado["estimado_gastos_usd"], editado["trabajadores_estimados"]) == ("5000.00", None)
    r = client.patch(f"/proyectos/{p['id']}", json={"fecha_fin_estimada": "2026-10-01"}, headers=h)
    assert r.status_code == 422  # antes del inicio estimado
    assert client.post("/proyectos", json={"nombre": "X", "estimado_gastos_mxn": "-1"}, headers=h).status_code == 422


def test_estimado_contra_real(client, base):
    h, b = base["h"], base["banco"]
    p = ok(client.post("/proyectos", json={"nombre": "Bodega", "estimado_ingresos_mxn": "10000",
                                           "estimado_gastos_mxn": "8000"}, headers=h), 201)
    entrada(client, h, p, b, "5000")
    salida(client, h, p, b, "2000")
    ok(client.post(f"/proyectos/{p['id']}/pendientes", json={"tipo": "por_cobrar", "concepto": "Estimación 2",
                                                             "moneda": "MXN", "monto": "5000"}, headers=h), 201)
    r = ok(client.get("/reportes/estimado-vs-real", params={"proyecto_id": p["id"]}, headers=h))
    fila = r["filas"][0]
    assert (fila["ingresos_estimados"], fila["ingresos_reales"], fila["avance_ingresos"]) == ("10000.00", "5000.00", "50.00")
    assert (fila["gastos_estimados"], fila["gastos_reales"], fila["avance_gastos"]) == ("8000.00", "2000.00", "25.00")
    assert (fila["resultado_estimado"], fila["resultado_real"], fila["por_cobrar"]) == ("2000.00", "3000.00", "5000.00")


# ------------------------------------------------------------------ cuentas por cobrar y por pagar
def test_cuentas_por_cobrar_y_por_pagar(client, base, admin):
    h, p = base["h"], base["proyecto"]
    cobrar = ok(client.post(f"/proyectos/{p['id']}/pendientes", json={
        "tipo": "por_cobrar", "concepto": "Estimación 3", "contraparte": "Cliente SA", "moneda": "MXN",
        "monto": "150000", "fecha_vencimiento": "2026-01-15"}, headers=h), 201)
    assert cobrar["vencida"] is True and cobrar["liquidada"] is False
    pagar = ok(client.post(f"/proyectos/{p['id']}/pendientes", json={
        "tipo": "por_pagar", "concepto": "Acero", "moneda": "USD", "monto": "2000"}, headers=h), 201)
    assert saldos_vacios(client, h, p)  # no afectan saldos

    r = ok(client.get("/reportes/cuentas-por-cobrar-pagar", headers=h))
    assert {t["moneda"]: (t["por_cobrar"], t["por_pagar"], t["diferencia"]) for t in r["totales"]} == \
        {"MXN": ("150000.00", "0.00", "150000.00"), "USD": ("0.00", "2000.00", "-2000.00")}
    assert r["filas"][0]["estado"] == "VENCIDA"

    liquidada = ok(client.patch(f"/pendientes/{cobrar['id']}", json={"liquidada": True}, headers=h))
    assert liquidada["liquidada"] is True and liquidada["fecha_liquidacion"] is not None
    assert len(ok(client.get("/pendientes", headers=h))) == 1  # solo pendientes por omisión
    assert len(ok(client.get("/pendientes", params={"estado": "todas"}, headers=h))) == 2
    assert client.delete(f"/pendientes/{pagar['id']}", headers=h).status_code == 204
    acciones = [i["accion"] for i in ok(client.get("/bitacora", params={"entidad": "Pendiente"},
                                                   headers=admin[1]))["items"]]
    assert acciones[:2] == ["ELIMINAR", "LIQUIDAR"]


def test_partida_valida(client, base):
    h, p = base["h"], base["proyecto"]
    url = f"/proyectos/{p['id']}/pendientes"
    assert client.post(url, json={"tipo": "por_cobrar", "concepto": "X", "moneda": "MXN", "monto": "0"},
                       headers=h).status_code == 422
    assert client.post(url, json={"tipo": "otro", "concepto": "X", "moneda": "MXN", "monto": "1"},
                       headers=h).status_code == 422


def saldos_vacios(client, h, p) -> bool:
    return ok(client.get(f"/proyectos/{p['id']}", headers=h))["saldos"] == []
