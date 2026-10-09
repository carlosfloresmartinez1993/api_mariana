/** Une clases de Tailwind ignorando valores vacíos. */
export function cn(...clases: (string | false | null | undefined)[]): string {
  return clases.filter(Boolean).join(" ");
}
