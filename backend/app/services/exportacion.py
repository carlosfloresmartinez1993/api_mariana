import csv
import io
from html import escape
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.tiempo import ahora


class Formato(StrEnum):
    JSON = "json"
    CSV = "csv"
    XLSX = "xlsx"
    PDF = "pdf"


@dataclass
class Reporte:
    titulo: str
    columnas: list[tuple[str, str]]  # (clave, etiqueta)
    filas: list[dict[str, Any]]
    # Una fila de totales por moneda (MXN y USD nunca se suman entre sí).
    totales: list[dict[str, Any]] = field(default_factory=list)
    parametros: dict[str, Any] = field(default_factory=dict)
    # Nombre de quien genera el reporte; se imprime al final.
    elaborado_por: str | None = None


MEDIA = {
    Formato.CSV: "text/csv; charset=utf-8",
    Formato.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    Formato.PDF: "application/pdf",
}


def _texto(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, Decimal):
        return f"{valor:,.2f}"
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d %H:%M")
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor)


def _filas_totales(reporte: Reporte) -> list[list[Any]]:
    filas = []
    for totales in reporte.totales:
        fila = [totales.get(clave) for clave, _ in reporte.columnas]
        if fila and fila[0] is None:
            fila[0] = "TOTAL"
        filas.append(fila)
    return filas


def _pie(reporte: Reporte) -> str | None:
    if not reporte.elaborado_por:
        return None
    return f"Elaborado por: {reporte.elaborado_por} — {ahora():%d/%m/%Y %H:%M}"


def a_csv(reporte: Reporte) -> bytes:
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    escritor.writerow([etiqueta for _, etiqueta in reporte.columnas])
    for fila in reporte.filas:
        escritor.writerow([fila.get(clave, "") if not isinstance(fila.get(clave), Decimal) else str(fila[clave])
                           for clave, _ in reporte.columnas])
    for totales in _filas_totales(reporte):
        escritor.writerow(["" if v is None else str(v) for v in totales])
    if pie := _pie(reporte):
        escritor.writerow([])
        escritor.writerow([pie])
    return buffer.getvalue().encode("utf-8-sig")  # BOM para que Excel respete acentos


def a_xlsx(reporte: Reporte) -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = reporte.titulo[:31]
    hoja.append([etiqueta for _, etiqueta in reporte.columnas])
    for celda in hoja[1]:
        celda.font = Font(bold=True)
    for fila in reporte.filas:
        hoja.append([_celda_excel(fila.get(clave)) for clave, _ in reporte.columnas])
        _rojo_si_negativo(hoja[hoja.max_row])
    for totales in _filas_totales(reporte):
        hoja.append([_celda_excel(v) for v in totales])
        for celda in hoja[hoja.max_row]:
            celda.font = Font(bold=True)
        _rojo_si_negativo(hoja[hoja.max_row], negritas=True)
    for columna in hoja.columns:
        ancho = max(len(_texto(c.value)) for c in columna)
        hoja.column_dimensions[columna[0].column_letter].width = min(max(ancho + 2, 10), 60)
    if pie := _pie(reporte):  # después de calcular anchos, para no ensanchar la primera columna
        hoja.append([])
        hoja.append([pie])
        hoja.cell(row=hoja.max_row, column=1).font = Font(italic=True)
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


ROJO = "C00000"


def _negativo(valor: Any) -> bool:
    return isinstance(valor, (Decimal, int, float)) and not isinstance(valor, bool) and valor < 0


def _rojo_si_negativo(celdas, negritas: bool = False) -> None:
    """Los saldos negativos (p. ej. un proyecto que usó dinero de otros) van en rojo."""
    for celda in celdas:
        if _negativo(celda.value):
            celda.font = Font(color=ROJO, bold=negritas)


def _celda_excel(valor: Any) -> Any:
    if isinstance(valor, datetime):
        return valor.replace(tzinfo=None)
    if isinstance(valor, (dict, list)):
        return str(valor)
    return valor


def _pdf(valor: Any) -> str:
    texto = escape(_texto(valor))
    return f'<font color="#{ROJO}">{texto}</font>' if _negativo(valor) else texto


def a_pdf(reporte: Reporte) -> bytes:
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(buffer, pagesize=landscape(letter), leftMargin=30, rightMargin=30)
    estilos = getSampleStyleSheet()
    celda = estilos["BodyText"].clone("celda", fontSize=7, leading=9)
    contenido: list[Any] = [Paragraph(reporte.titulo, estilos["Title"])]
    if reporte.parametros:
        filtros = ", ".join(f"{k}: {_texto(v)}" for k, v in reporte.parametros.items() if v is not None)
        contenido.append(Paragraph(filtros, estilos["Normal"]))
    contenido.append(Spacer(1, 10))

    datos = [[Paragraph(f"<b>{etiqueta}</b>", celda) for _, etiqueta in reporte.columnas]]
    for fila in reporte.filas:
        datos.append([Paragraph(_pdf(fila.get(clave)), celda) for clave, _ in reporte.columnas])
    for totales in _filas_totales(reporte):
        datos.append([Paragraph(f"<b>{_pdf(v)}</b>", celda) for v in totales])
    if len(datos) == 1:
        datos.append([Paragraph("Sin registros", celda)] + [""] * (len(reporte.columnas) - 1))

    tabla = Table(datos, repeatRows=1)
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.black),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    contenido.append(tabla)
    if pie := _pie(reporte):
        contenido += [Spacer(1, 14), Paragraph(f"<i>{pie}</i>", estilos["Normal"])]
    documento.build(contenido)
    return buffer.getvalue()


def exportar(reporte: Reporte, formato: Formato) -> bytes:
    return {Formato.CSV: a_csv, Formato.XLSX: a_xlsx, Formato.PDF: a_pdf}[formato](reporte)
