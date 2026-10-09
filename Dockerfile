# Imagen única para producción: compila el frontend (React) y lo sirve junto con la API.
# La API queda en /api y la aplicación web en /. Ver render.yaml.

# ---------- 1. Frontend ----------
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 2. Backend + frontend compilado ----------
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIR=/app/static

WORKDIR /app
RUN useradd --create-home --uid 1000 app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY --from=frontend /frontend/dist ./static

USER app
EXPOSE 8000
CMD ["sh", "scripts/arranque.sh"]
