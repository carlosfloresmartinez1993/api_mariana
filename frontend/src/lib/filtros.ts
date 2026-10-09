import { useCallback } from "react";
import { useSearchParams } from "react-router";

/**
 * Filtros guardados en la URL (?empresa_id=…&desde=…): se pueden compartir como enlace
 * y sobreviven a recargar la página. Cambiar un filtro regresa a la primera página.
 */
export function useFiltros<K extends string>(claves: readonly K[]) {
  const [params, setParams] = useSearchParams();

  const filtros = Object.fromEntries(claves.map((k) => [k, params.get(k) ?? ""])) as Record<K, string>;
  const offset = Number(params.get("offset") ?? 0) || 0;

  const cambiar = useCallback(
    (cambios: Partial<Record<K | "offset", string | number>>) => {
      setParams(
        (prev) => {
          const sig = new URLSearchParams(prev);
          for (const [k, v] of Object.entries(cambios)) {
            if (v === "" || v === undefined || v === null || (k === "offset" && v === 0)) sig.delete(k);
            else sig.set(k, String(v));
          }
          if (!("offset" in cambios)) sig.delete("offset");
          return sig;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  const limpiar = useCallback(() => setParams(new URLSearchParams(), { replace: true }), [setParams]);
  const activos = claves.some((k) => filtros[k] !== "");

  return { filtros, offset, cambiar, limpiar, activos };
}
