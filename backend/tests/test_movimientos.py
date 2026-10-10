from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app

from tests.helpers import (
    crear_cuenta,
    crear_empresa,
    crear_proyecto,
    entrada,
    ok,
    salida,
    saldo_cuenta,
    saldos_proyecto,
)


@pytest.fixture
def escenario(client, juan):
    """Empresa con banco y caja en MXN, banco en USD, y un proyecto aún sin vincular."""
    h = juan[1]
    empresa = crear_empresa(client, h)
    return {
        "h": h,
        "empresa": empresa,
        "banco": crear_cuenta(client, h, empresa["id"], "banco", "MXN", banco="BBVA"),
        "caja": crear_cuenta(client, h, empresa["id"], "caja", "MXN"),
        "usd": crear_cuenta(client, h, empresa["id"], "banco", "USD", banco="BBVA"),
        "proyecto": crear_proyecto(client, h),
    }


# ------------------------------------------------------------------ entradas
def test_entrada_con_porcentaje_llega_neta_a_la_cuenta(client, escenario):
    e = escenario
    mov = entrada(client, e["h"], e["proyecto"], e["banco"], "100000", "3")
    assert (mov["monto"], mov["porcentaje_gasto"], mov["monto_gasto"], mov["monto_neto"]) == \
        ("100000.00", "3.00", "3000.00", "97000.00")
    assert mov["moneda"] == "MXN"
    assert saldo_cuenta(client, e["h"], e["banco"]) == "97000.00"
    saldo = saldos_proyecto(client, e["h"], e["proyecto"])["MXN"]
    assert (saldo["ingresos"], saldo["gastos"], saldo["salidas"], saldo["saldo"]) == \
        ("97000.00", "3000.00", "0.00", "97000.00")


def test_cada_entrada_lleva_su_propio_porcentaje(client, escenario):
    e = escenario
    entrada(client, e["h"], e["proyecto"], e["banco"], "1000", "2.5")
    entrada(client, e["h"], e["proyecto"], e["banco"], "1000")
    entrada(client, e["h"], e["proyecto"], e["caja"], "333.33", "10")
    saldo = saldos_proyecto(client, e["h"], e["proyecto"])["MXN"]
    assert saldo["gastos"] == "58.33"  # 25.00 + 0 + 33.33
    assert saldo["ingresos"] == "2275.00"  # 975 + 1000 + 300


def test_la_empresa_se_vincula_sola_al_proyecto(client, escenario, admin):
    e = escenario
    entrada(client, e["h"], e["proyecto"], e["banco"], "100")
    proyecto = ok(client.get(f"/proyectos/{e['proyecto']['id']}", headers=e["h"]))
    assert [x["nombre"] for x in proyecto["empresas"]] == ["Constructora Norte"]
    vinculos = ok(client.get("/bitacora", params={"accion": "VINCULAR"}, headers=admin[1]))["items"]
    assert len(vinculos) == 1 and vinculos[0]["detalle"]["automatico"] is True
    entrada(client, e["h"], e["proyecto"], e["banco"], "100")  # no se vuelve a vincular
    assert ok(client.get("/bitacora", params={"accion": "VINCULAR"}, headers=admin[1]))["total"] == 1


def test_efectivo_va_a_caja_y_transferencia_a_banco(client, escenario):
    e = escenario
    entrada(client, e["h"], e["proyecto"], e["banco"], "100", forma="efectivo", esperado=422)
    entrada(client, e["h"], e["proyecto"], e["caja"], "100", forma="transferencia", esperado=422)


def test_la_cuenta_debe_ser_de_la_empresa(client, escenario):
    e = escenario
    otra = crear_empresa(client, e["h"], "Otra")
    entrada(client, e["h"], e["proyecto"], e["banco"], "100", empresa_id=otra["id"], esperado=422)


@pytest.mark.parametrize("porcentaje", ["-1", "100", "3.555"])
def test_porcentaje_invalido(client, escenario, porcentaje):
    e = escenario
    entrada(client, e["h"], e["proyecto"], e["banco"], "100", porcentaje, esperado=422)


def test_fecha_futura(client, escenario):
    e = escenario
    manana = (date.today() + timedelta(days=2)).isoformat()
    entrada(client, e["h"], e["proyecto"], e["banco"], "100", fecha=manana, esperado=422)


# ------------------------------------------------------------------ salidas
def test_salida_descuenta_del_proyecto_y_de_la_cuenta(client, escenario):
    e = escenario
    entrada(client, e["h"], e["proyecto"], e["banco"], "1000", "10")
    salida(client, e["h"], e["proyecto"], e["banco"], "400", beneficiario="Cementos SA")
    assert saldo_cuenta(client, e["h"], e["banco"]) == "500.00"
    assert saldos_proyecto(client, e["h"], e["proyecto"])["MXN"]["saldo"] == "500.00"


def test_salida_no_puede_exceder_el_saldo_del_proyecto(client, escenario):
    e = escenario
    otro = crear_proyecto(client, e["h"], "Otro")
    entrada(client, e["h"], otro, e["banco"], "1000000")  # la cuenta tiene dinero, pero de otro proyecto
    entrada(client, e["h"], e["proyecto"], e["banco"], "100")
    r = salida(client, e["h"], e["proyecto"], e["banco"], "100.01", esperado=422)
    assert "proyecto" in r["detail"]


def test_salida_no_puede_exceder_el_saldo_de_la_cuenta(client, escenario):
    e = escenario
    entrada(client, e["h"], e["proyecto"], e["caja"], "1000")  # el dinero está en la caja
    r = salida(client, e["h"], e["proyecto"], e["banco"], "10", esperado=422)
    assert "cuenta" in r["detail"]


def test_monedas_separadas(client, escenario):
    e = escenario
    entrada(client, e["h"], e["proyecto"], e["usd"], "500")
    saldos = saldos_proyecto(client, e["h"], e["proyecto"])
    assert set(saldos) == {"USD"}
    entrada(client, e["h"], crear_proyecto(client, e["h"], "Otro"), e["banco"], "1000")
    salida(client, e["h"], e["proyecto"], e["banco"], "1", esperado=422)  # el proyecto no tiene pesos


def test_el_dinero_del_proyecto_solo_sale_de_la_empresa_donde_entro(client, escenario):
    """El caso que motivó la regla: un proyecto con dinero en otra empresa no puede usar el de esta."""
    e = escenario
    otra = crear_empresa(client, e["h"], "Inmobiliaria Pacífico")
    caja_otra = crear_cuenta(client, e["h"], otra["id"], "caja", "USD")
    torre, palmas = e["proyecto"], crear_proyecto(client, e["h"], "Las Palmas")
    entrada(client, e["h"], torre, e["usd"], "19800")
    entrada(client, e["h"], palmas, caja_otra, "7840")
    r = salida(client, e["h"], palmas, e["usd"], "7840", esperado=422)  # Palmas no tiene USD en esta empresa
    assert "Constructora Norte" in r["detail"] and "Las Palmas" in r["detail"]
    salida(client, e["h"], palmas, caja_otra, "7840")
    proyecto = ok(client.get(f"/proyectos/{palmas['id']}", headers=e["h"]))
    assert [(s["empresa_nombre"], s["moneda"], s["saldo"]) for s in proyecto["saldos_por_empresa"]] ==         [("Inmobiliaria Pacífico", "USD", "0.00")]


def test_saldo_del_proyecto_por_empresa(client, escenario):
    e = escenario
    otra = crear_empresa(client, e["h"], "Otra")
    banco_otra = crear_cuenta(client, e["h"], otra["id"], "banco", "MXN")
    entrada(client, e["h"], e["proyecto"], e["banco"], "1000")
    entrada(client, e["h"], e["proyecto"], banco_otra, "300")
    salida(client, e["h"], e["proyecto"], banco_otra, "300")
    salida(client, e["h"], e["proyecto"], banco_otra, "0.01", esperado=422)  # en Otra ya no le queda nada
    proyecto = ok(client.get(f"/proyectos/{e['proyecto']['id']}", headers=e["h"]))
    assert [(s["empresa_nombre"], s["saldo"]) for s in proyecto["saldos_por_empresa"]] ==         [("Constructora Norte", "1000.00"), ("Otra", "0.00")]
    assert proyecto["saldos"][0]["saldo"] == "1000.00"


def test_deposito_de_caja_al_banco_con_salida_y_entrada(client, escenario):
    """Sin traspasos: el efectivo se lleva al banco con una salida de la caja y una entrada sin % al banco."""
    e = escenario
    entrada(client, e["h"], e["proyecto"], e["caja"], "1000")
    salida(client, e["h"], e["proyecto"], e["caja"], "600", concepto="Depósito al banco")
    entrada(client, e["h"], e["proyecto"], e["banco"], "600", concepto="Depósito de la caja")
    assert saldo_cuenta(client, e["h"], e["caja"]) == "400.00"
    assert saldo_cuenta(client, e["h"], e["banco"]) == "600.00"
    assert saldos_proyecto(client, e["h"], e["proyecto"])["MXN"]["saldo"] == "1000.00"
    assert client.post("/traspasos", json={}, headers=e["h"]).status_code in (404, 405)


def test_salida_requiere_concepto(client, escenario):
    e = escenario
    entrada(client, e["h"], e["proyecto"], e["banco"], "100")
    salida(client, e["h"], e["proyecto"], e["banco"], "10", concepto="   ", esperado=422)


# ------------------------------------------------------------------ anulaciones y ediciones
def test_anular_entrada_y_salida(client, escenario, admin):
    e = escenario
    ent = entrada(client, e["h"], e["proyecto"], e["banco"], "1000")
    sal = salida(client, e["h"], e["proyecto"], e["banco"], "300")
    # No se puede anular la entrada: el proyecto y la cuenta quedarían en −300.
    r = client.post(f"/entradas/{ent['id']}/anular", json={"motivo": "Captura duplicada"}, headers=e["h"])
    assert r.status_code == 422
    anulada = ok(client.post(f"/salidas/{sal['id']}/anular", json={"motivo": "Pago cancelado"}, headers=e["h"]))
    assert anulada["anulado"] is True and anulada["motivo_anulacion"] == "Pago cancelado"
    ok(client.post(f"/entradas/{ent['id']}/anular", json={"motivo": "Captura duplicada"}, headers=e["h"]))
    assert saldo_cuenta(client, e["h"], e["banco"]) == "0.00"
    assert ok(client.get("/entradas", params={"estado": "anulados"}, headers=e["h"]))["total"] == 1
    assert ok(client.get("/entradas", headers=e["h"]))["total"] == 0
    r = client.post(f"/entradas/{ent['id']}/anular", json={"motivo": "Otra vez"}, headers=e["h"])
    assert r.status_code == 422
    assert ok(client.get("/bitacora", params={"accion": "ANULAR"}, headers=admin[1]))["total"] == 2


def test_anular_requiere_motivo(client, escenario):
    e = escenario
    ent = entrada(client, e["h"], e["proyecto"], e["banco"], "1000")
    assert client.post(f"/entradas/{ent['id']}/anular", json={"motivo": ""}, headers=e["h"]).status_code == 422


def test_editar_entrada_recalcula_el_neto(client, escenario):
    e = escenario
    ent = entrada(client, e["h"], e["proyecto"], e["banco"], "1000", "5")
    editada = ok(client.patch(f"/entradas/{ent['id']}", json={"monto": "2000", "porcentaje_gasto": "1"},
                              headers=e["h"]))
    assert (editada["monto_gasto"], editada["monto_neto"]) == ("20.00", "1980.00")
    assert saldo_cuenta(client, e["h"], e["banco"]) == "1980.00"


def test_editar_no_puede_dejar_saldos_negativos(client, escenario):
    e = escenario
    ent = entrada(client, e["h"], e["proyecto"], e["banco"], "1000")
    sal = salida(client, e["h"], e["proyecto"], e["banco"], "900")
    assert client.patch(f"/entradas/{ent['id']}", json={"monto": "800"}, headers=e["h"]).status_code == 422
    assert client.patch(f"/salidas/{sal['id']}", json={"monto": "1000.01"}, headers=e["h"]).status_code == 422
    ok(client.patch(f"/salidas/{sal['id']}", json={"monto": "1000", "beneficiario": "Juan Pérez"}, headers=e["h"]))


def test_solo_el_autor_o_un_admin_corrige(client, escenario, pedro, admin):
    e = escenario
    ent = entrada(client, e["h"], e["proyecto"], e["banco"], "1000")
    assert ent["creado_por_nombre"] == "Juan"
    assert client.patch(f"/entradas/{ent['id']}", json={"concepto": "x"}, headers=pedro[1]).status_code == 403
    r = client.post(f"/entradas/{ent['id']}/anular", json={"motivo": "No es mía"}, headers=pedro[1])
    assert r.status_code == 403
    ok(client.patch(f"/entradas/{ent['id']}", json={"concepto": "Anticipo"}, headers=admin[1]))
    # Pedro sí ve y captura sobre lo de Juan
    assert ok(client.get("/entradas", headers=pedro[1]))["total"] == 1
    salida(client, pedro[1], e["proyecto"], e["banco"], "100")


def test_filtros_de_movimientos(client, escenario):
    e = escenario
    entrada(client, e["h"], e["proyecto"], e["banco"], "100", concepto="Anticipo obra")
    entrada(client, e["h"], e["proyecto"], e["caja"], "50", fecha="2026-01-15")
    entrada(client, e["h"], e["proyecto"], e["usd"], "10")
    h = e["h"]
    assert ok(client.get("/entradas", params={"moneda": "USD"}, headers=h))["total"] == 1
    assert ok(client.get("/entradas", params={"forma": "efectivo"}, headers=h))["total"] == 1
    assert ok(client.get("/entradas", params={"q": "anticipo"}, headers=h))["total"] == 1
    assert ok(client.get("/entradas", params={"desde": "2026-01-01", "hasta": "2026-01-31"}, headers=h))["total"] == 1
    assert ok(client.get("/entradas", params={"cuenta_id": e["banco"]["id"]}, headers=h))["total"] == 1


def test_salidas_simultaneas_no_rebasan_el_saldo(client, escenario):
    """El bloqueo de cuenta y proyecto hace que la segunda salida vea la primera y se rechace."""
    e = escenario
    entrada(client, e["h"], e["proyecto"], e["banco"], "100")
    datos = {"proyecto_id": e["proyecto"]["id"], "empresa_id": e["empresa"]["id"], "cuenta_id": e["banco"]["id"],
             "fecha": date.today().isoformat(), "forma": "transferencia", "monto": "60", "concepto": "Pago"}

    def pagar(_):
        with TestClient(app) as c:
            return c.post("/salidas", json=datos, headers=e["h"]).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        codigos = sorted(pool.map(pagar, range(4)))
    assert codigos == [201, 422, 422, 422]
    assert saldo_cuenta(client, e["h"], e["banco"]) == "40.00"
