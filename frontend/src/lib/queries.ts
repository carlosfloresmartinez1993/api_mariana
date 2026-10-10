import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { Cuenta, Empresa, Pagina, Proyecto, Usuario } from "./types";

// Catálogos para selectores. El volumen esperado es pequeño (decenas o cientos).

export function useEmpresasCatalogo() {
  return useQuery({
    queryKey: ["empresas", "catalogo"],
    queryFn: () => api.get<Pagina<Empresa>>("/empresas", { limit: 500 }).then((p) => p.items),
  });
}

export function useProyectosCatalogo() {
  return useQuery({
    queryKey: ["proyectos", "catalogo"],
    queryFn: () => api.get<Pagina<Proyecto>>("/proyectos", { limit: 500 }).then((p) => p.items),
  });
}

/** Todas las cuentas con su saldo actual. */
export function useCuentas(empresaId?: string) {
  return useQuery({
    queryKey: ["cuentas", empresaId ?? "todas"],
    queryFn: () => api.get<Cuenta[]>("/cuentas", { empresa_id: empresaId }),
  });
}

export function useUsuariosCatalogo() {
  return useQuery({
    queryKey: ["usuarios", "catalogo"],
    queryFn: () => api.get<Usuario[]>("/usuarios/catalogo"),
  });
}

/** Tras cualquier cambio de dinero cambian saldos en muchas pantallas: se invalida todo lo relacionado. */
export function useInvalidarDinero() {
  const qc = useQueryClient();
  return () =>
    Promise.all(
      ["empresas", "cuentas", "proyectos", "entradas", "salidas", "reportes", "resumen"].map((k) =>
        qc.invalidateQueries({ queryKey: [k] }),
      ),
    );
}
