"""Comandos de administración.

    python -m app.cli inicializar   # crea (o restablece) el superusuario desde SUPERUSUARIO_*

La API hace lo mismo al arrancar; este comando sirve para hacerlo a mano o desde un script.
"""

import argparse
import sys

from app.core.config import settings
from app.core.errors import ErrorDominio
from app.db.session import SessionLocal
from app.services.usuarios import asegurar_superusuario


def inicializar(_: argparse.Namespace) -> int:
    if not settings.SUPERUSUARIO_CORREO or not settings.SUPERUSUARIO_PASSWORD:
        print("inicializar: define SUPERUSUARIO_CORREO y SUPERUSUARIO_PASSWORD", file=sys.stderr)
        return 1
    try:
        with SessionLocal() as db:
            print("inicializar:", asegurar_superusuario(
                db,
                correo=settings.SUPERUSUARIO_CORREO,
                password=settings.SUPERUSUARIO_PASSWORD.get_secret_value(),
                nombre=settings.SUPERUSUARIO_NOMBRE,
                restablecer=settings.SUPERUSUARIO_RESTABLECER,
            ))
    except ErrorDominio as exc:
        print(f"inicializar: {exc.detalle}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_init = sub.add_parser("inicializar", help="Crea o restablece el superusuario desde SUPERUSUARIO_*")
    p_init.set_defaults(func=inicializar)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
