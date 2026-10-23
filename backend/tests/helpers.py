from typing import Any

from fastapi.testclient import TestClient

from app.core.tiempo import hoy

# La fecha del negocio (TIMEZONE), no la del servidor: en CI (UTC) ya puede ser mañana.
HOY = hoy().isoformat()


def ok(respuesta, codigo: int = 200) -> Any:
    assert respuesta.status_code == codigo, respuesta.text
    return respuesta.json()


def crear_empresa(client: TestClient, h: dict, nombre: str = "Constructora Norte") -> dict:
    return ok(client.post("/empresas", json={"nombre": nombre}, headers=h), 201)


def crear_cuenta(client: TestClient, h: dict, empresa_id: str, tipo: str = "banco", moneda: str = "MXN",
                 **extra) -> dict:
    datos = {"empresa_id": empresa_id, "tipo": tipo, "moneda": moneda, **extra}
    return ok(client.post("/cuentas", json=datos, headers=h), 201)


def crear_proyecto(client: TestClient, h: dict, nombre: str = "Torre Centro", **extra) -> dict:
    return ok(client.post("/proyectos", json={"nombre": nombre, **extra}, headers=h), 201)


def entrada(client: TestClient, h: dict, proyecto: dict, cuenta: dict, monto: str, porcentaje: str = "0",
            fecha: str = HOY, esperado: int = 201, **extra):
    datos = {"proyecto_id": proyecto["id"], "empresa_id": cuenta["empresa_id"], "cuenta_id": cuenta["id"],
             "fecha": fecha, "forma": "efectivo" if cuenta["tipo"] == "caja" else "transferencia", "monto": monto,
             "porcentaje_gasto": porcentaje, **extra}
    return ok(client.post("/entradas", json=datos, headers=h), esperado)


def salida(client: TestClient, h: dict, proyecto: dict, cuenta: dict, monto: str, fecha: str = HOY,
           esperado: int = 201, **extra):
    datos = {"proyecto_id": proyecto["id"], "empresa_id": cuenta["empresa_id"], "cuenta_id": cuenta["id"],
             "fecha": fecha, "forma": "efectivo" if cuenta["tipo"] == "caja" else "transferencia", "monto": monto,
             "concepto": "Pago a proveedor", **extra}
    return ok(client.post("/salidas", json=datos, headers=h), esperado)


def saldo_cuenta(client: TestClient, h: dict, cuenta: dict) -> str:
    return ok(client.get(f"/cuentas/{cuenta['id']}", headers=h))["saldo"]


def saldos_proyecto(client: TestClient, h: dict, proyecto: dict) -> dict[str, dict]:
    return {s["moneda"]: s for s in ok(client.get(f"/proyectos/{proyecto['id']}", headers=h))["saldos"]}
