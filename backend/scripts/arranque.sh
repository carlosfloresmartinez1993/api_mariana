#!/bin/sh
# Arranque en producción (Dockerfile de la raíz / Render / Railway).
set -e

# 1. Migraciones pendientes
alembic upgrade head

# 2. Datos de demostración (solo si SEED_DEMO=true y la base no tiene empresas)
if [ "$SEED_DEMO" = "true" ]; then
  python -m app.seed || echo "seed: omitido (la base ya tiene datos)"
fi

# 3. API en /api y frontend en /. Al arrancar, la API crea el superusuario desde SUPERUSUARIO_* si no existe.
exec uvicorn app.servidor:servidor --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
