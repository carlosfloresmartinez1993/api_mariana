import pytest

from tests.helpers import crear_cuenta, crear_empresa, crear_proyecto, entrada, ok, salida

PDF = b"%PDF-1.4\n%prueba\n"
XML = b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?><cfdi:Comprobante/>'
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20


@pytest.fixture
def mov(client, juan):
    h = juan[1]
    banco = crear_cuenta(client, h, crear_empresa(client, h)["id"])
    proyecto = crear_proyecto(client, h)
    return {"h": h, "entrada": entrada(client, h, proyecto, banco, "1000"),
            "salida": salida(client, h, proyecto, banco, "100"), "proyecto": proyecto, "banco": banco}


def _subir(client, h, ruta, contenido, nombre="factura.pdf"):
    return client.put(f"{ruta}/factura", files={"archivo": (nombre, contenido)}, headers=h)


def test_requiere_factura_es_opcional(client, mov):
    assert mov["entrada"]["requiere_factura"] is False and mov["entrada"]["factura_nombre"] is None
    e = entrada(client, mov["h"], mov["proyecto"], mov["banco"], "50", requiere_factura=True)
    assert e["requiere_factura"] is True
    editada = ok(client.patch(f"/salidas/{mov['salida']['id']}", json={"requiere_factura": True}, headers=mov["h"]))
    assert editada["requiere_factura"] is True


@pytest.mark.parametrize("tipo", ["entradas", "salidas"])
def test_subir_ver_reemplazar_y_quitar_factura(client, mov, tipo):
    h = mov["h"]
    ruta = f"/{tipo}/{mov[tipo[:-1]]['id']}"
    r = ok(_subir(client, h, ruta, PDF, "C:\\Users\\yo\\Factura Ñandú.pdf"))
    assert (r["factura_nombre"], r["factura_tipo"], r["factura_tamano"]) == ("Factura Ñandú.pdf", "application/pdf",
                                                                             len(PDF))
    descarga = client.get(f"{ruta}/factura", headers=h)
    assert descarga.status_code == 200 and descarga.content == PDF
    assert descarga.headers["content-type"] == "application/pdf"
    r = ok(_subir(client, h, ruta, XML, "cfdi.xml"))
    assert (r["factura_nombre"], r["factura_tipo"]) == ("cfdi.xml", "application/xml")
    assert client.get(f"{ruta}/factura", headers=h).content == XML
    r = ok(client.delete(f"{ruta}/factura", headers=h))
    assert r["factura_nombre"] is None
    assert client.get(f"{ruta}/factura", headers=h).status_code == 404


def test_tipos_aceptados_por_contenido(client, mov):
    ruta, h = f"/entradas/{mov['entrada']['id']}", mov["h"]
    assert ok(_subir(client, h, ruta, PNG, "foto"))["factura_nombre"] == "foto.png"
    r = _subir(client, h, ruta, b"MZ ejecutable", "factura.pdf")  # extension de PDF, contenido no
    assert r.status_code == 422 and "PDF, XML, JPG o PNG" in r.json()["detail"]
    assert _subir(client, h, ruta, b"%PDF-" + b"0" * (1024 * 1024)).status_code == 422  # > MAX_DOCUMENTO_MB


def test_solo_el_autor_o_un_admin_sube_factura(client, mov, pedro, admin):
    ruta = f"/entradas/{mov['entrada']['id']}"
    assert _subir(client, pedro[1], ruta, PDF).status_code == 403
    ok(_subir(client, admin[1], ruta, PDF))
    assert client.get(f"{ruta}/factura", headers=pedro[1]).status_code == 200  # todos pueden verla


def test_filtro_de_factura(client, mov):
    h = mov["h"]
    p, b = mov["proyecto"], mov["banco"]
    entrada(client, h, p, b, "10", requiere_factura=True)
    con_archivo = entrada(client, h, p, b, "20", requiere_factura=True)
    ok(_subir(client, h, f"/entradas/{con_archivo['id']}", PDF))
    total = lambda f: ok(client.get("/entradas", params={"factura": f}, headers=h))["total"]  # noqa: E731
    assert (total("requerida"), total("pendiente"), total("adjunta"), total("sin")) == (2, 1, 1, 1)


def test_bitacora_de_facturas(client, mov, admin):
    ruta = f"/salidas/{mov['salida']['id']}"
    ok(_subir(client, mov["h"], ruta, PDF))
    ok(client.delete(f"{ruta}/factura", headers=mov["h"]))
    acciones = [i["accion"] for i in ok(client.get("/bitacora", params={"entidad_id": mov["salida"]["id"]},
                                                   headers=admin[1]))["items"]]
    assert acciones[:2] == ["ELIMINAR_FACTURA", "SUBIR_FACTURA"]
