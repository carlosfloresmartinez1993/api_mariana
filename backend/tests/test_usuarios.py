import pytest

NUEVO = {"nombre": "Ana López", "correo": "ana@test.com", "password": "Clave123"}


@pytest.mark.parametrize("password", ["corta1", "SoloLetras", "12345678"])
def test_politica_de_password(client, admin, password):
    r = client.post("/usuarios", json={**NUEVO, "password": password}, headers=admin[1])
    assert r.status_code == 422


def test_password_de_8_caracteres_con_letras_y_numeros(client, admin):
    r = client.post("/usuarios", json=NUEVO, headers=admin[1])
    assert r.status_code == 201
    assert r.json()["rol"] == "contador"
    assert "password" not in r.json() and "password_hash" not in r.json()


def test_correo_duplicado(client, admin):
    assert client.post("/usuarios", json=NUEVO, headers=admin[1]).status_code == 201
    r = client.post("/usuarios", json={**NUEVO, "correo": "ANA@test.com"}, headers=admin[1])
    assert r.status_code == 409


def test_admin_crea_contadores_pero_no_admins(client, admin):
    r = client.post("/usuarios", json={**NUEVO, "rol": "admin"}, headers=admin[1])
    assert r.status_code == 403


def test_superusuario_crea_admins(client, superusuario):
    r = client.post("/usuarios", json={**NUEVO, "rol": "admin"}, headers=superusuario[1])
    assert r.status_code == 201
    assert r.json()["rol"] == "admin"


def test_nadie_crea_otro_superusuario_por_la_api(client, superusuario):
    r = client.post("/usuarios", json={**NUEVO, "rol": "superusuario"}, headers=superusuario[1])
    assert r.status_code == 422


def test_admin_no_administra_a_otros_admins(client, admin, superusuario):
    otro = client.post("/usuarios", json={**NUEVO, "rol": "admin"}, headers=superusuario[1]).json()
    h = admin[1]
    assert client.patch(f"/usuarios/{otro['id']}", json={"nombre": "X"}, headers=h).status_code == 403
    assert client.post(f"/usuarios/{otro['id']}/desactivar", headers=h).status_code == 403
    assert client.post(f"/usuarios/{otro['id']}/restablecer-password", json={"nueva": "Otra1234"},
                       headers=h).status_code == 403


def test_admin_no_puede_ascender_a_un_contador(client, admin, juan):
    r = client.patch(f"/usuarios/{juan[0].id}", json={"rol": "admin"}, headers=admin[1])
    assert r.status_code == 403


def test_superusuario_cambia_roles(client, superusuario, juan):
    r = client.patch(f"/usuarios/{juan[0].id}", json={"rol": "admin"}, headers=superusuario[1])
    assert r.status_code == 200 and r.json()["rol"] == "admin"


def test_nadie_toca_al_superusuario(client, superusuario, admin):
    su = superusuario[0]
    assert client.patch(f"/usuarios/{su.id}", json={"nombre": "X"}, headers=admin[1]).status_code == 403
    assert client.post(f"/usuarios/{su.id}/desactivar", headers=admin[1]).status_code == 403
    assert client.patch(f"/usuarios/{su.id}", json={"rol": "contador"}, headers=superusuario[1]).status_code == 403
    assert client.post(f"/usuarios/{su.id}/desactivar", headers=superusuario[1]).status_code == 422


def test_contador_no_administra_usuarios(client, juan, pedro):
    assert client.get("/usuarios", headers=juan[1]).status_code == 403
    assert client.post("/usuarios", json=NUEVO, headers=juan[1]).status_code == 403
    assert client.post(f"/usuarios/{pedro[0].id}/desactivar", headers=juan[1]).status_code == 403


def test_catalogo_visible_para_todos(client, juan, pedro, admin):
    r = client.get("/usuarios/catalogo", headers=juan[1])
    assert r.status_code == 200
    assert {u["correo"] for u in r.json()} == {"juan@test.com", "pedro@test.com", "admin@test.com"}
