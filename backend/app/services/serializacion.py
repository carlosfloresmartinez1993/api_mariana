from decimal import Decimal
from typing import Any

from fastapi.encoders import jsonable_encoder


def a_json(valor: Any) -> Any:
    """Convierte a tipos JSON conservando los montos como texto exacto (sin float)."""
    return jsonable_encoder(valor, custom_encoder={Decimal: str})
