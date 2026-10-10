# Control de Empresas y Proyectos

Control de entradas, salidas y saldos por empresa, cuenta (banco o caja, en MXN o USD) y proyecto.

- Análisis, reglas de negocio y modelo de datos: [docs/Análisis y modelo de datos.md](docs/Análisis%20y%20modelo%20de%20datos.md)
- Stack: el mismo de *Integra · Control de Clientes* (FastAPI + SQLAlchemy + PostgreSQL, React + Vite + Tailwind). Interfaz en blanco y negro.

```
backend/    API REST (FastAPI), migraciones (Alembic) y pruebas (pytest)
frontend/   aplicación web (React + TypeScript)
Dockerfile  imagen única: API en /api y frontend en /
```

## Qué hace

- **Empresas** (solo con nombre) con **cuentas de banco** (varias) y **cajas de efectivo** (una por moneda), en MXN o USD. La moneda se fija al crear la cuenta y no cambia. Las cuentas empiezan en cero: no hay saldo inicial, el dinero que ya había se registra como una entrada de un proyecto («Saldo de apertura»).
- **Proyectos** (solo con nombre), en una o varias empresas. La empresa se vincula sola al capturar.
- **Entradas** a un proyecto: empresa, cuenta, transferencia o efectivo y un % de gasto opcional distinto en cada una. El gasto se lo queda el proveedor: a la cuenta llega el neto.
- **Salidas** de un proyecto desde una cuenta de una empresa. El dinero de un proyecto queda en la empresa donde entró: la salida no puede rebasar el saldo del proyecto **en esa empresa y moneda**, ni el de la cuenta.
- **Sin traspasos**: para llevar efectivo de la caja al banco se registra una salida de la caja y una entrada sin % al banco, del mismo proyecto.
- Nada se borra: los movimientos se **anulan con motivo**.
- **Reportes** con periodo opcional (sin periodo = todo), en pantalla, Excel, PDF o CSV: saldo por proyecto, historial de un proyecto, saldo por proyecto y empresa, saldo por cuenta (con totales de cajas y bancos), cuadre (por empresa y moneda: saldo de las cuentas = saldo de los proyectos), gastos acumulados / por proyecto / por empresa, ingresos (neto) por proyecto / por empresa.

## Usuarios y roles

| Rol | Puede |
|-----|-------|
| Superusuario | Todo. Es único y se crea al arrancar la API con `SUPERUSUARIO_CORREO` / `SUPERUSUARIO_PASSWORD`. Da de alta administradores |
| Administrador | Ve y corrige todo, da de alta contadores y consulta la bitácora |
| Contador | Ve todo y captura; solo corrige o anula lo que él registró |

Todo lo que hace cualquier usuario (incluidos los inicios de sesión) queda en la bitácora, que la base de datos no deja modificar ni borrar.

### Superusuario

Al arrancar, la API revisa si existe el superusuario y, si no, lo crea con las variables de entorno. Funciona igual en local, Docker, Render o Railway:

```
SUPERUSUARIO_CORREO=super@empresa.com
SUPERUSUARIO_PASSWORD=Clave123      # 8 caracteres o más, con letras y números
SUPERUSUARIO_NOMBRE=Superusuario
```

Si se olvida la contraseña: poner `SUPERUSUARIO_RESTABLECER=true`, reiniciar (se vuelven a aplicar el correo y la contraseña del entorno) y después quitar la variable. También se puede ejecutar a mano con `python -m app.cli inicializar`.

## Desarrollo local

Requisitos: Python 3.13, Node 22, PostgreSQL 16 o superior y [uv](https://docs.astral.sh/uv/).

```bash
# Backend (carpeta backend/)
uv venv --python 3.13 .venv
uv pip install -r requirements-dev.txt --python .venv/Scripts/python.exe
copy .env.example .env                      # DATABASE_URL, SECRET_KEY, SUPERUSUARIO_*
.venv\Scripts\alembic upgrade head
.venv\Scripts\python -m uvicorn app.main:app --port 8000

# Frontend (carpeta frontend/)
npm ci
npm run dev                                 # http://localhost:5173 (proxy /api → :8000)

# Pruebas (usan la base <nombre>_test, p. ej. empresas_test)
.venv\Scripts\python -m pytest
```

Las bases `empresas` y `empresas_test` deben existir (`CREATE DATABASE empresas;`).

**Datos de demostración**: `.venv\Scripts\python -m app.seed` carga empresas, cuentas, proyectos y movimientos (solo si la base no tiene empresas) y los usuarios `admin@demo.local`, `ana@demo.local` y `luis@demo.local`, con la contraseña definida en `DEMO_PASSWORD` de [backend/app/seed.py](backend/app/seed.py). En Docker se activa con `SEED_DEMO=true`. Para empezar en limpio: borrar y volver a crear la base, y `alembic upgrade head`.

## Dependencias

`requirements.in` tiene los rangos aceptados; `requirements.txt` las versiones exactas:

```bash
uv pip compile requirements.in --universal --python-version 3.13 -o requirements.txt
uv pip compile requirements-dev.in --universal --python-version 3.13 -o requirements-dev.txt
```

## Migraciones

```bash
.venv\Scripts\alembic revision --autogenerate -m "descripcion" --rev-id 0002
.venv\Scripts\alembic upgrade head
.venv\Scripts\alembic check     # debe decir «No new upgrade operations detected»
```

## Despliegue

- **Render**: `render.yaml` (servicio web Docker + PostgreSQL). Pide `SUPERUSUARIO_CORREO` y `SUPERUSUARIO_PASSWORD` al crear el Blueprint.
- **Railway**: el mismo `Dockerfile` + PostgreSQL; definir `DATABASE_URL`, `SECRET_KEY`, `ENVIRONMENT=production`, `DOCS_ENABLED=false`, `FORWARDED_ALLOW_IPS=*` y `SUPERUSUARIO_*`.

Al arrancar, el contenedor aplica las migraciones (`alembic upgrade head`) y levanta la API, que crea el superusuario si hace falta. La integración continua (`.github/workflows/ci.yml`) corre migraciones, `alembic check`, pruebas, el build del frontend y el de la imagen.
