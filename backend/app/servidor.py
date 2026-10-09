"""Punto de entrada para producción con un solo servicio (Render o Railway).

Sirve la API bajo /api y el build del frontend (React) en la raíz, igual que el
proxy de Vite en desarrollo, así el navegador habla con un solo dominio y no
hace falta CORS:

    uvicorn app.servidor:servidor --host 0.0.0.0 --port 8000

En desarrollo se sigue usando app.main:app directamente.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.main import app as api

# Las sub-aplicaciones montadas no reciben los eventos de arranque/parada,
# así que el ciclo de vida de la API (verificar el superusuario) se ejecuta aquí.
servidor = FastAPI(lifespan=api.router.lifespan_context, docs_url=None, redoc_url=None, openapi_url=None)
servidor.mount("/api", api)

frontend = settings.FRONTEND_DIR.resolve()
index = frontend / "index.html"

if (frontend / "assets").is_dir():
    # Archivos con hash en el nombre: se pueden cachear sin límite.
    servidor.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")


@servidor.get("/{ruta:path}", include_in_schema=False)
def spa(ruta: str):
    """Archivos públicos (favicon…) si existen; para cualquier otra ruta, index.html (rutas de React)."""
    if not index.is_file():
        raise HTTPException(status_code=404, detail="Frontend no compilado")
    archivo = (frontend / ruta).resolve()
    if ruta and archivo.is_file() and archivo.is_relative_to(frontend):
        return FileResponse(archivo)
    return FileResponse(index, headers={"Cache-Control": "no-cache"})
