const numero2 = new Intl.NumberFormat("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fechaCorta = new Intl.DateTimeFormat("es-MX", { day: "2-digit", month: "short", year: "numeric" });
const fechaHora = new Intl.DateTimeFormat("es-MX", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/** "1234.5" + "MXN" → "$1,234.50 MXN". Sin moneda: "$1,234.50". */
export function dinero(valor: string | number | null | undefined, moneda?: string): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  const n = Number(valor);
  if (!Number.isFinite(n)) return String(valor);
  const texto = `${n < 0 ? "-" : ""}$${numero2.format(Math.abs(n))}`;
  return moneda ? `${texto} ${moneda}` : texto;
}

export function numero(valor: string | number): string {
  return numero2.format(Number(valor));
}

export function porcentaje(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  return `${Number(valor).toFixed(2)} %`;
}

/** "2026-10-05" → "05 oct 2026" (sin desfase de zona horaria). */
export function fecha(valor: string | null | undefined): string {
  if (!valor) return "—";
  const [a, m, d] = valor.slice(0, 10).split("-").map(Number);
  return fechaCorta.format(new Date(a, m - 1, d));
}

export function fechaHoraLocal(valor: string | null | undefined): string {
  if (!valor) return "—";
  return fechaHora.format(new Date(valor));
}

/** Fecha de hoy en formato AAAA-MM-DD según el reloj del navegador. */
export function hoyISO(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** Monto escrito por el usuario → centavos enteros (o null si no es válido). */
export function aCentavos(texto: string): number | null {
  const limpio = texto.replace(/[\s,$]/g, "");
  if (!/^\d+(\.\d{0,2})?$/.test(limpio)) return null;
  return Math.round(Number(limpio) * 100);
}

/** Gasto y neto de una entrada, igual que la base de datos: gasto = round(monto × % / 100, 2). */
export function calcularEntrada(monto: string, porcentajeGasto: string): { gasto: number; neto: number } | null {
  const centavos = aCentavos(monto);
  const pct = Number(porcentajeGasto || 0);
  if (centavos === null || !Number.isFinite(pct)) return null;
  const gasto = Math.round((centavos * pct) / 100);
  return { gasto: gasto / 100, neto: (centavos - gasto) / 100 };
}

/**
 * Formatea un monto mientras se escribe: separador de miles automático y hasta 2 decimales.
 * "1234567.5" → "1,234,567.5". Solo acepta dígitos y un punto decimal.
 */
export function formatearMientrasEscribe(texto: string): string {
  const limpio = texto.replace(/[^\d.]/g, "");
  const [entero, ...resto] = limpio.split(".");
  const enteroSinCeros = entero.replace(/^0+(?=\d)/, "");
  const conMiles = enteroSinCeros.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return resto.length ? `${conMiles}.${resto.join("").slice(0, 2)}` : conMiles;
}

/** Monto escrito ("1,234.50") → texto para la API ("1234.50"). */
export function montoParaApi(texto: string): string {
  return texto.replace(/,/g, "");
}

/** Monto de la API ("1234.5") → texto para editar ("1,234.50"). */
export function montoParaEditar(valor: string | null | undefined): string {
  if (!valor) return "";
  const [entero, decimales = ""] = Number(valor).toFixed(2).split(".");
  return `${formatearMientrasEscribe(entero)}.${decimales}`;
}

export function tamanoArchivo(bytes: number | null | undefined): string {
  if (!bytes) return "";
  return bytes < 1024 * 1024 ? `${Math.ceil(bytes / 1024)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
