from enum import StrEnum

from sqlalchemy import Enum as SAEnum


class Rol(StrEnum):
    SUPERUSUARIO = "superusuario"
    ADMIN = "admin"
    CONTADOR = "contador"


class Moneda(StrEnum):
    MXN = "MXN"
    USD = "USD"


class TipoCuenta(StrEnum):
    BANCO = "banco"
    CAJA = "caja"


class Forma(StrEnum):
    """Cómo se movió el dinero. Transferencia → cuenta de banco; efectivo → caja."""

    TRANSFERENCIA = "transferencia"
    EFECTIVO = "efectivo"

    @property
    def tipo_cuenta(self) -> TipoCuenta:
        return TipoCuenta.BANCO if self == Forma.TRANSFERENCIA else TipoCuenta.CAJA


class TipoPendiente(StrEnum):
    """Cuenta pendiente de un proyecto: lo que le deben (por cobrar) o lo que debe (por pagar)."""

    POR_COBRAR = "por_cobrar"
    POR_PAGAR = "por_pagar"


class AccionBitacora(StrEnum):
    """Catálogo cerrado de acciones de la bitácora. La entidad afectada va en su propia columna."""

    INICIO_SESION = "INICIO_SESION"
    INICIO_SESION_FALLIDO = "INICIO_SESION_FALLIDO"
    CAMBIO_PASSWORD = "CAMBIO_PASSWORD"
    CREAR = "CREAR"
    EDITAR = "EDITAR"
    ACTIVAR = "ACTIVAR"
    DESACTIVAR = "DESACTIVAR"
    ANULAR = "ANULAR"
    VINCULAR = "VINCULAR"
    DESVINCULAR = "DESVINCULAR"
    CAMBIO_SALDO_INICIAL = "CAMBIO_SALDO_INICIAL"  # ya no se usa; se conserva por los registros antiguos
    SUBIR_FACTURA = "SUBIR_FACTURA"
    ELIMINAR_FACTURA = "ELIMINAR_FACTURA"
    LIQUIDAR = "LIQUIDAR"
    ELIMINAR = "ELIMINAR"


def enum_columna(enum_cls: type[StrEnum], nombre: str, largo: int) -> SAEnum:
    """Enum guardado como varchar + CHECK (evita ALTER TYPE al agregar valores)."""
    return SAEnum(
        enum_cls,
        name=nombre,
        native_enum=False,
        create_constraint=True,
        length=largo,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )
