const fechaCorta = new Intl.DateTimeFormat("es-MX", { day: "2-digit", month: "short", year: "numeric" });
const fechaHora = new Intl.DateTimeFormat("es-MX", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

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
