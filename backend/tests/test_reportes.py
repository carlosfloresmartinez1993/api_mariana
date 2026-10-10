import pytest

from tests.helpers import crear_cuenta, crear_empresa, crear_proyecto, entrada, ok, salida


@pytest.fixture
def datos(client, juan):
    """Dos empresas, dos proyectos, MXN y USD. Fechas fijas en enero y febrero de 2026."""
    h = juan[1]
    norte, sur = crear_empresa(client, h, "Norte"), crear_empresa(client, h, "Sur")
    c = {
        "norte_banco": crear_cuenta(client, h, norte["id"], "banco", "MXN", banco="BBVA"),
        "norte_caja": crear_cuenta(client, h, norte["id"], "caja", "MXN"),
        "sur_banco": crear_cuenta(client, h, sur["id"], "banco", "MXN", banco="Banorte"),
        "sur_usd": crear_cuenta(client, h, sur["id"], "banco", "USD", banco="Banorte"),
    }
    torre, casa = crear_proyecto(client, h, "Torre"), crear_proyecto(client, h, "Casa")
    entrada(client, h, torre, c["norte_banco"], "10000", "3", fecha="2026-01-10")   # gasto 300, neto 9700
    entrada(client, h, torre, c["sur_banco"], "5000", "2", fecha="2026-02-05")      # gasto 100, neto 4900
    entrada(client, h, casa, c["norte_caja"], "2000", fecha="2026-02-10")           # neto 2000
    entrada(client, h, torre, c["sur_usd"], "1000", "1", fecha="2026-02-11")        # gasto 10, neto 990 USD
    salida(client, h, torre, c["norte_banco"], "1500", fecha="2026-02-15")
    # Deposito del efectivo al banco: salida de la caja y entrada sin % al banco, del mismo proyecto.
    salida(client, h, casa, c["norte_caja"], "500", fecha="2026-02-20", concepto="Deposito al banco")
    entrada(client, h, casa, c["norte_banco"], "500", fecha="2026-02-20", concepto="Deposito de la caja")
    return {"h": h, "norte": norte, "sur": sur, "torre": torre, "casa": casa, **c}


def _reporte(client, h, ruta, **params):
    return ok(client.get(f"/reportes/{ruta}", params=params, headers=h))


def _por(filas, *claves):
    return {tuple(f[k] for k in claves): f for f in filas}


def test_saldo_por_proyecto(client, datos):
    r = _reporte(client, datos["h"], "saldos-proyectos")
    filas = _por(r["filas"], "proyecto", "moneda")
    torre = filas[("Torre", "MXN")]
    assert (torre["ingresos"], torre["gastos"], torre["salidas"], torre["saldo"]) == \
        ("14600.00", "400.00", "1500.00", "13100.00")
    assert filas[("Torre", "USD")]["saldo"] == "990.00"
    assert (filas[("Casa", "MXN")]["ingresos"], filas[("Casa", "MXN")]["saldo"]) == ("2500.00", "2000.00")
    totales = _por(r["totales"], "moneda")
    assert totales[("MXN",)]["saldo"] == "15100.00" and totales[("USD",)]["saldo"] == "990.00"


def test_saldo_por_proyecto_en_un_periodo_y_por_empresa(client, datos):
    r = _reporte(client, datos["h"], "saldos-proyectos", desde="2026-02-01", hasta="2026-02-28",
                 empresa_id=datos["norte"]["id"])
    filas = _por(r["filas"], "proyecto", "moneda")
    assert set(filas) == {("Torre", "MXN"), ("Casa", "MXN")}
    assert filas[("Torre", "MXN")]["saldo"] == "-1500.00"  # en febrero, en Norte, Torre solo tuvo la salida
    assert r["parametros"]["Empresa"] == "Norte"


def test_saldo_por_proyecto_y_empresa(client, datos):
    r = _reporte(client, datos["h"], "saldos-proyectos", por_empresa="true")
    filas = {(f["proyecto"], f["empresa"], f["moneda"]): f["saldo"] for f in r["filas"]}
    assert filas == {("Casa", "Norte", "MXN"): "2000.00", ("Torre", "Norte", "MXN"): "8200.00",
                     ("Torre", "Sur", "MXN"): "4900.00", ("Torre", "Sur", "USD"): "990.00"}


def test_cuadre_cuentas_contra_proyectos(client, datos):
    """Por empresa y moneda: entradas - salidas = saldo de las cuentas = saldo de los proyectos."""
    r = _reporte(client, datos["h"], "cuadre")
    filas = _por(r["filas"], "empresa", "moneda")
    norte = filas[("Norte", "MXN")]
    assert (norte["entradas"], norte["salidas"], norte["cuentas"], norte["proyectos"], norte["diferencia"]) ==         ("12200.00", "2000.00", "10200.00", "10200.00", "0.00")
    assert all(f["estado"] == "Cuadra" for f in r["filas"] + r["totales"])
    assert {t["moneda"]: t["cuentas"] for t in r["totales"]} == {"MXN": "15100.00", "USD": "990.00"}
    al_corte = _reporte(client, datos["h"], "cuadre", hasta="2026-01-31")
    assert [(f["empresa"], f["moneda"], f["cuentas"]) for f in al_corte["filas"] if f["cuentas"] != "0.00"] ==         [("Norte", "MXN", "9700.00")]


def test_historial_del_proyecto_con_saldo_acumulado(client, datos):
    r = _reporte(client, datos["h"], f"historial-proyecto/{datos['torre']['id']}")
    filas = r["filas"]
    assert [(f["tipo"], f["empresa"], f["cuenta"], f["moneda"], f["saldo"]) for f in filas] == [
        ("Entrada", "Norte", "BBVA MXN", "MXN", "9700.00"),
        ("Entrada", "Sur", "Banorte MXN", "MXN", "14600.00"),
        ("Entrada", "Sur", "Banorte USD", "USD", "990.00"),
        ("Salida", "Norte", "BBVA MXN", "MXN", "13100.00"),
    ]
    assert filas[0]["gasto"] == "300.00" and filas[0]["bruto"] == "10000.00"
    assert filas[0]["registrado_por"] == "Juan"
    totales = _por(r["totales"], "moneda")
    assert totales[("MXN",)]["entrada"] == "14600.00" and totales[("MXN",)]["saldo"] == "13100.00"


def test_historial_con_periodo_empieza_con_el_saldo_anterior(client, datos):
    r = _reporte(client, datos["h"], f"historial-proyecto/{datos['torre']['id']}", desde="2026-02-01")
    assert r["filas"][0]["tipo"] == "Saldo anterior" and r["filas"][0]["saldo"] == "9700.00"
    assert r["filas"][-1]["saldo"] == "13100.00"


def test_saldo_por_cuenta_con_totales_de_cajas_y_bancos(client, datos):
    r = _reporte(client, datos["h"], "saldos-cuentas")
    filas = _por(r["filas"], "empresa", "cuenta")
    caja = filas[("Norte", "Caja MXN")]
    assert (caja["entradas"], caja["salidas"], caja["saldo"]) == ("2000.00", "500.00", "1500.00")
    assert filas[("Norte", "BBVA MXN")]["saldo"] == "8700.00"  # 9700 + 500 - 1500
    assert "anterior" not in {c["clave"] for c in r["columnas"]}
    assert filas[("Sur", "Banorte MXN")]["saldo"] == "4900.00"
    totales = {t["empresa"]: t["saldo"] for t in r["totales"]}
    assert totales == {"Total cajas MXN": "1500.00", "Total bancos MXN": "13600.00", "TOTAL MXN": "15100.00",
                       "Total bancos USD": "990.00", "TOTAL USD": "990.00"}


def test_saldo_por_cuenta_al_corte(client, datos):
    r = _reporte(client, datos["h"], "saldos-cuentas", hasta="2026-01-31")
    assert {t["empresa"]: t["saldo"] for t in r["totales"]}["TOTAL MXN"] == "9700.00"  # 100 inicial + 9700


def test_gastos(client, datos):
    h = datos["h"]
    por_proyecto = _reporte(client, h, "gastos", agrupar="proyecto")
    assert [(f["proyecto"], f["moneda"], f["total"]) for f in por_proyecto["filas"]] == \
        [("Casa", "MXN", "0.00"), ("Torre", "MXN", "400.00"), ("Torre", "USD", "10.00")]
    por_empresa = _reporte(client, h, "gastos", agrupar="empresa")
    assert [(f["empresa"], f["moneda"], f["total"]) for f in por_empresa["filas"]] == \
        [("Norte", "MXN", "300.00"), ("Sur", "MXN", "100.00"), ("Sur", "USD", "10.00")]
    acumulados = _reporte(client, h, "gastos", agrupar="moneda")
    assert [(f["moneda"], f["total"]) for f in acumulados["filas"]] == [("MXN", "400.00"), ("USD", "10.00")]
    febrero = _reporte(client, h, "gastos", agrupar="empresa", desde="2026-02-01")
    assert [(f["empresa"], f["total"]) for f in febrero["filas"]] == [("Norte", "0.00"), ("Sur", "100.00"),
                                                                    ("Sur", "10.00")]


def test_ingresos_en_neto(client, datos):
    h = datos["h"]
    r = _reporte(client, h, "ingresos", agrupar="empresa")
    assert [(f["empresa"], f["moneda"], f["entradas"], f["total"]) for f in r["filas"]] == \
        [("Norte", "MXN", 3, "12200.00"), ("Sur", "MXN", 1, "4900.00"), ("Sur", "USD", 1, "990.00")]
    r = _reporte(client, h, "ingresos", agrupar="proyecto", proyecto_id=datos["casa"]["id"])
    assert [(f["proyecto"], f["total"]) for f in r["filas"]] == [("Casa", "2500.00")]


def test_los_anulados_no_cuentan(client, datos):
    h = datos["h"]
    salida_id = ok(client.get("/salidas", params={"proyecto_id": datos["torre"]["id"]}, headers=h))["items"][0]["id"]
    ok(client.post(f"/salidas/{salida_id}/anular", json={"motivo": "Error"}, headers=h))
    r = _reporte(client, h, "saldos-proyectos", proyecto_id=datos["torre"]["id"])
    assert _por(r["filas"], "moneda")[("MXN",)]["saldo"] == "14600.00"


def test_resumen_de_inicio(client, datos):
    r = ok(client.get("/reportes/resumen", headers=datos["h"]))
    assert r["dinero"] == [{"moneda": "MXN", "cajas": "1500.00", "bancos": "13600.00", "total": "15100.00"},
                           {"moneda": "USD", "cajas": "0.00", "bancos": "990.00", "total": "990.00"}]
    assert r["empresas"] == 2 and r["proyectos"] == 2


@pytest.mark.parametrize(("formato", "tipo"), [("csv", "text/csv"), ("xlsx", "spreadsheetml"),
                                               ("pdf", "application/pdf")])
def test_exportaciones(client, datos, formato, tipo):
    for ruta in ("saldos-proyectos", "saldos-cuentas", "cuadre", f"historial-proyecto/{datos['torre']['id']}", "gastos",
                 "ingresos"):
        r = client.get(f"/reportes/{ruta}", params={"formato": formato}, headers=datos["h"])
        assert r.status_code == 200, (ruta, r.text)
        assert tipo in r.headers["content-type"]
        assert "attachment" in r.headers["content-disposition"]
        assert len(r.content) > 100


def test_periodo_invertido(client, datos):
    r = client.get("/reportes/gastos", params={"desde": "2026-03-01", "hasta": "2026-01-01"}, headers=datos["h"])
    assert r.status_code == 422
