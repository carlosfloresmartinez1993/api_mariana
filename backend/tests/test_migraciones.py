"""Las migraciones deben dejar la base igual que los modelos.

`alembic check` no detecta cambios en los CHECK (p. ej. un valor nuevo en un enum), ni en los triggers.
Esta prueba compara lo que PostgreSQL reporta después de `alembic upgrade head` contra `create_all`.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.db.base import Base
from app.db.session import engine

BACKEND = Path(__file__).parents[1]

ESQUEMA = {
    "checks": "SELECT conrelid::regclass::text || '.' || conname, pg_get_constraintdef(oid) "
              "FROM pg_constraint WHERE contype IN ('c', 'f', 'u', 'p') AND connamespace = 'public'::regnamespace",
    "indices": "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public'",
    "triggers": "SELECT tgname, pg_get_triggerdef(oid) FROM pg_trigger WHERE NOT tgisinternal",
    "columnas": "SELECT table_name || '.' || column_name, data_type || coalesce(column_default, '') || is_nullable "
                "|| coalesce(generation_expression, '') FROM information_schema.columns WHERE table_schema = 'public'",
}


def _reiniciar() -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))


def _describir() -> dict[str, dict[str, str]]:
    with engine.connect() as conn:
        return {clave: dict(conn.execute(text(sql)).all()) for clave, sql in ESQUEMA.items()}


def test_migraciones_igual_que_los_modelos():
    _reiniciar()
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    try:
        command.upgrade(config, "head")
        migrado = _describir()
        _reiniciar()
        Base.metadata.create_all(engine)
        modelos = _describir()
    finally:
        # Las demás pruebas esperan el esquema de create_all.
        _reiniciar()
        Base.metadata.create_all(engine)
    migrado["columnas"].pop("alembic_version.version_num", None)
    migrado["indices"].pop("alembic_version_pkc", None)
    migrado["checks"].pop("alembic_version.alembic_version_pkc", None)
    for clave in ESQUEMA:
        assert migrado[clave] == modelos[clave], clave
