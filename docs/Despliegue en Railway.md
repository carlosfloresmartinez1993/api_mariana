# Despliegue en Railway

Guía para publicar **Control de Empresas y Proyectos** en Railway desde el repositorio
[`carlosfloresmartinez1993/api_mariana`](https://github.com/carlosfloresmartinez1993/api_mariana).

El sistema es **una sola imagen Docker** (API FastAPI + frontend React ya compilado), una base
**PostgreSQL** y un **Bucket** S3 para las facturas. No hace falta modificar código: todo se configura
con variables de entorno. `railway.json` (en la raíz) ya indica a Railway que use el `Dockerfile` y que
revise `/api/health` antes de dar por bueno un despliegue. `render.yaml` es solo para Render.

```
Railway (proyecto)
├── Servicio web   ← este repositorio (Dockerfile + railway.json)
├── PostgreSQL     ← datos
└── Bucket         ← facturas (la BD guarda solo la ruta)
```

---

## 1. Crear el proyecto y el servicio

1. En Railway: **New Project → Deploy from GitHub repo** → elegir `carlosfloresmartinez1993/api_mariana`.
   Si no aparece, dar acceso a la app de Railway en GitHub (**Settings → Applications → Railway → Configure**).
2. Rama: `main`.
3. Recomendado: en el servicio, **Settings → Deploy**, activar **Wait for CI**. Así solo se publica lo que
   pasó las pruebas de GitHub (`.github/workflows/ci.yml`).

## 2. Agregar la base de datos

1. En el proyecto: **+ New → Database → PostgreSQL**.
2. No hay que crear tablas: al arrancar, el servicio aplica las migraciones (`alembic upgrade head`).
3. **Respaldos**: en el servicio de PostgreSQL, sección **Backups**, programar respaldos automáticos
   (según el plan). Antes de cada cambio que toque la base, sacar además un respaldo manual (ver §7).

## 3. Agregar el bucket para las facturas

1. En el proyecto: **+ New → Bucket**.
2. Debe quedar **privado**: la aplicación entrega cada factura solo a usuarios con sesión; nadie debe poder
   abrirla con un enlace directo al bucket.
3. Anotar los datos de conexión que muestra el bucket: **nombre**, **endpoint**, **región**, **access key**
   y **secret key**.

## 4. Variables de entorno del servicio web

En el servicio → **Variables**. Donde se pueda, usar **referencias** (`${{Postgres.DATABASE_URL}}`) para que
se actualicen solas si cambian; el panel las sugiere al escribir `${{`.

### Obligatorias

| Variable | Valor | Notas |
|---|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | `Postgres` es el nombre del servicio de base de datos. Se acepta `postgresql://`; la app lo convierte sola. |
| `SECRET_KEY` | cadena aleatoria de 64 caracteres | Firma las sesiones. Generar con `python -c "import secrets; print(secrets.token_hex(32))"`. No reutilizar la de Render. |
| `ENVIRONMENT` | `production` | |
| `DOCS_ENABLED` | `false` | Oculta la documentación interactiva de la API. |
| `TIMEZONE` | `America/Tijuana` | Define qué es «hoy» (fechas futuras, periodos de reportes). |
| `FORWARDED_ALLOW_IPS` | `*` | Railway pone un proxy delante; así el límite de intentos de acceso ve la IP real. |
| `SUPERUSUARIO_CORREO` | correo del superusuario | Se crea al arrancar si no existe. |
| `SUPERUSUARIO_PASSWORD` | contraseña | Mínimo 8 caracteres, con letras y números. |
| `SUPERUSUARIO_NOMBRE` | nombre | Aparece en la bitácora y en «Elaborado por» de los reportes. |
| `ALMACENAMIENTO` | `s3` | Guarda las facturas en el bucket. |
| `S3_BUCKET` | nombre del bucket | |
| `S3_ENDPOINT_URL` | endpoint del bucket | Con `https://`. |
| `S3_REGION` | región del bucket | Si no muestra ninguna: `auto`. |
| `S3_ACCESS_KEY_ID` | access key del bucket | |
| `S3_SECRET_ACCESS_KEY` | secret key del bucket | |

Si falta alguna `S3_*`, el servicio **no arranca** y el log dice cuál falta (`ALMACENAMIENTO=s3 requiere: …`).

### Opcionales

| Variable | Valor | Para qué |
|---|---|---|
| `S3_PREFIJO` | p. ej. `produccion/` | Carpeta dentro del bucket (útil si el bucket se comparte). |
| `MAX_DOCUMENTO_MB` | `5` | Tamaño máximo de cada factura. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Duración de la sesión. |
| `SUPERUSUARIO_RESTABLECER` | `true` | Solo para recuperar el acceso: vuelve a aplicar la contraseña del entorno al arrancar. Quitarla después. |
| `SEED_DEMO` | `false` | Con `true` carga datos de demostración. **No usar en producción.** |

`PORT` lo pone Railway; no hay que definirlo.

## 5. Dominio

En el servicio → **Settings → Networking → Generate Domain** (o conectar un dominio propio). La aplicación
queda en la raíz y la API en `/api` (mismo dominio, sin CORS).

## 6. Primer arranque y comprobación

En **Deployments → View logs** deben aparecer, en este orden:

1. `Running upgrade … -> 0004, facturas` (migraciones).
2. `superusuario creado: <correo>`.
3. `Uvicorn running on http://0.0.0.0:…`.

Después:

- Abrir `https://<dominio>/api/health` → `{"status":"ok"}`.
- Entrar con el superusuario y crear los administradores y contadores en **Usuarios**.
- Subir una factura de prueba, hacer **Redeploy** y comprobar que la factura sigue abriéndose
  (confirma que se guarda en el bucket y no en el disco del contenedor).

## 7. Cambios futuros con datos reales

1. Los cambios se prueban primero en local (`pytest` y revisión en el navegador).
2. Si el cambio toca la base, va en una **migración de Alembic**; nunca se modifica la base de producción a mano.
3. **Respaldo antes de desplegar** un cambio que toque la base. Con las credenciales de PostgreSQL de Railway
   (pestaña *Connect*, URL pública):

   ```bash
   pg_dump --format=custom --no-owner --file=respaldo-AAAA-MM-DD.dump "<DATABASE_PUBLIC_URL>"
   ```

   Para restaurar (en una base vacía):

   ```bash
   pg_restore --no-owner --dbname="<URL de la base destino>" respaldo-AAAA-MM-DD.dump
   ```

4. `git push` a `main` → Railway construye la imagen, aplica las migraciones al arrancar y publica.
5. **Rollback** en Railway regresa el *código* a un despliegue anterior, pero **no deshace las migraciones**:
   por eso el respaldo del paso 3.

## Problemas comunes

| Síntoma | Causa | Qué hacer |
|---|---|---|
| El servicio no arranca: `ALMACENAMIENTO=s3 requiere: …` | Falta una variable `S3_*` | Agregarla en Variables. |
| No se puede entrar con el superusuario | Variables vacías, con espacios o contraseña sin números | Revisar el log del arranque; corregir y usar `SUPERUSUARIO_RESTABLECER=true` una vez. |
| Error de conexión a la base | `DATABASE_URL` mal referenciada | Usar `${{Postgres.DATABASE_URL}}` con el nombre real del servicio de base de datos. |
| El healthcheck falla en el primer despliegue | La base aún no estaba lista | **Redeploy**; las migraciones se aplican al arrancar. |
