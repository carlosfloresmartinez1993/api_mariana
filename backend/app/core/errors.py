class ErrorDominio(Exception):
    """Error de negocio que se traduce a una respuesta HTTP con {"detail": ...}."""

    status_code = 400

    def __init__(self, detalle: str):
        super().__init__(detalle)
        self.detalle = detalle


class NoEncontrado(ErrorDominio):
    status_code = 404


class Prohibido(ErrorDominio):
    status_code = 403


class Conflicto(ErrorDominio):
    status_code = 409


class ReglaNegocio(ErrorDominio):
    status_code = 422
