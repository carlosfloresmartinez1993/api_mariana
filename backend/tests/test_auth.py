from tests.conftest import PASSWORD


def test_login_correcto_y_me(client, juan):
    r = client.post("/auth/login", data={"username": "JUAN@test.com", "password": PASSWORD})
    assert r.status_code == 200
    token = r.json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.json()["correo"] == "juan@test.com"
    assert r.json()["rol"] == "contador"


def test_login_incorrecto_no_revela_si_existe_el_correo(client, juan):
    r1 = client.post("/auth/login", data={"username": "juan@test.com", "password": "mala1234"})
    r2 = client.post("/auth/login", data={"username": "nadie@test.com", "password": "mala1234"})
    assert r1.status_code == r2.status_code == 401
    assert r1.json() == r2.json()


def test_token_invalido(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401


def test_usuario_desactivado_pierde_acceso_inmediato(client, admin, juan):
    usuario, h = juan
    assert client.get("/auth/me", headers=h).status_code == 200
    assert client.post(f"/usuarios/{usuario.id}/desactivar", headers=admin[1]).status_code == 200
    assert client.get("/auth/me", headers=h).status_code == 401
    r = client.post("/auth/login", data={"username": "juan@test.com", "password": PASSWORD})
    assert r.status_code == 401


def test_cambiar_password(client, juan):
    r = client.post("/auth/cambiar-password", json={"actual": PASSWORD, "nueva": "Nueva123"}, headers=juan[1])
    assert r.status_code == 204
    r = client.post("/auth/login", data={"username": "juan@test.com", "password": "Nueva123"})
    assert r.status_code == 200


def test_cambiar_password_exige_la_actual(client, juan):
    r = client.post("/auth/cambiar-password", json={"actual": "otra1234", "nueva": "Nueva123"}, headers=juan[1])
    assert r.status_code == 400
