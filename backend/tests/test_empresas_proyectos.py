from tests.helpers import crear_cuenta, crear_empresa, crear_proyecto, entrada, ok


def test_empresa_solo_con_nombre(client, juan):
    empresa = crear_empresa(client, juan[1], "  Constructora   Norte ")
    assert empresa["nombre"] == "Constructora Norte"
    assert empresa["creado_por_nombre"] == "Juan"
    detalle = ok(client.get(f"/empresas/{empresa['id']}", headers=juan[1]))
    assert detalle["num_cuentas"] == 0 and detalle["num_proyectos"] == 0 and detalle["saldos"] == []


def test_nombre_de_empresa_unico_sin_importar_mayusculas(client, juan):
    crear_empresa(client, juan[1], "Constructora Norte")
    r = client.post("/empresas", json={"nombre": "CONSTRUCTORA NORTE"}, headers=juan[1])
    assert r.status_code == 409


def test_todos_ven_todo_pero_cada_contador_corrige_solo_lo_suyo(client, juan, pedro, admin):
    empresa = crear_empresa(client, juan[1])
    lista = ok(client.get("/empresas", headers=pedro[1]))
    assert [e["nombre"] for e in lista["items"]] == ["Constructora Norte"]
    r = client.patch(f"/empresas/{empresa['id']}", json={"nombre": "Otra"}, headers=pedro[1])
    assert r.status_code == 403 and "Juan" in r.json()["detail"]
    assert client.post(f"/empresas/{empresa['id']}/desactivar", headers=pedro[1]).status_code == 403
    ok(client.patch(f"/empresas/{empresa['id']}", json={"nombre": "Norte SA"}, headers=juan[1]))
    ok(client.patch(f"/empresas/{empresa['id']}", json={"nombre": "Norte SA de CV"}, headers=admin[1]))


def test_resumen_de_empresa_con_saldos_por_moneda(client, juan):
    h = juan[1]
    empresa = crear_empresa(client, h)
    proyecto = crear_proyecto(client, h)
    entrada(client, h, proyecto, crear_cuenta(client, h, empresa["id"], "banco", "MXN"), "1000")
    entrada(client, h, proyecto, crear_cuenta(client, h, empresa["id"], "caja", "MXN"), "250.50")
    entrada(client, h, proyecto, crear_cuenta(client, h, empresa["id"], "caja", "USD"), "10")
    detalle = ok(client.get(f"/empresas/{empresa['id']}", headers=h))
    assert detalle["num_cuentas"] == 3
    assert {s["moneda"]: s["saldo"] for s in detalle["saldos"]} == {"MXN": "1250.50", "USD": "10.00"}


def test_proyecto_solo_con_nombre_y_vinculo_manual(client, juan):
    h = juan[1]
    empresa = crear_empresa(client, h)
    proyecto = crear_proyecto(client, h)
    assert proyecto["empresas"] == [] and proyecto["saldos"] == []
    proyecto = ok(client.post(f"/proyectos/{proyecto['id']}/empresas", json={"empresa_id": empresa["id"]}, headers=h))
    assert [e["nombre"] for e in proyecto["empresas"]] == ["Constructora Norte"]
    r = client.post(f"/proyectos/{proyecto['id']}/empresas", json={"empresa_id": empresa["id"]}, headers=h)
    assert r.status_code == 409
    proyecto = ok(client.delete(f"/proyectos/{proyecto['id']}/empresas/{empresa['id']}", headers=h))
    assert proyecto["empresas"] == []


def test_un_proyecto_en_varias_empresas(client, juan):
    h = juan[1]
    a, b = crear_empresa(client, h, "A"), crear_empresa(client, h, "B")
    proyecto = crear_proyecto(client, h, empresa_ids=[a["id"], b["id"]])
    assert [e["nombre"] for e in proyecto["empresas"]] == ["A", "B"]
    filtrados = ok(client.get("/proyectos", params={"empresa_id": b["id"]}, headers=h))
    assert [p["nombre"] for p in filtrados["items"]] == ["Torre Centro"]


def test_no_se_desvincula_si_hay_movimientos(client, juan):
    h = juan[1]
    empresa = crear_empresa(client, h)
    banco = crear_cuenta(client, h, empresa["id"])
    proyecto = crear_proyecto(client, h)
    entrada(client, h, proyecto, banco, "100")
    r = client.delete(f"/proyectos/{proyecto['id']}/empresas/{empresa['id']}", headers=h)
    assert r.status_code == 422


def test_proyecto_desactivado_no_recibe_movimientos(client, juan):
    h = juan[1]
    banco = crear_cuenta(client, h, crear_empresa(client, h)["id"])
    proyecto = crear_proyecto(client, h)
    ok(client.post(f"/proyectos/{proyecto['id']}/desactivar", headers=h))
    entrada(client, h, proyecto, banco, "100", esperado=422)


def test_bitacora_registra_altas_y_cambios(client, juan, admin):
    empresa = crear_empresa(client, juan[1])
    ok(client.patch(f"/empresas/{empresa['id']}", json={"nombre": "Nuevo nombre"}, headers=juan[1]))
    items = ok(client.get("/bitacora", params={"entidad_id": empresa["id"]}, headers=admin[1]))["items"]
    assert [(i["accion"], i["usuario_nombre"]) for i in items] == [("EDITAR", "Juan"), ("CREAR", "Juan")]
    assert items[0]["detalle"]["antes"]["nombre"] == "Constructora Norte"
