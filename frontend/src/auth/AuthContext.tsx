import { createContext, use, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, onSesionExpirada, token } from "../lib/api";
import type { Usuario } from "../lib/types";

interface Sesion {
  usuario: Usuario | null;
  cargando: boolean;
  /** Administrador o superusuario. */
  esAdmin: boolean;
  esSuperusuario: boolean;
  /** Mensaje para mostrar en el login cuando la sesión se cerró sola. */
  aviso: string | null;
  entrar: (correo: string, password: string) => Promise<void>;
  salir: () => void;
  recargar: () => Promise<void>;
}

const AuthContext = createContext<Sesion | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [cargando, setCargando] = useState(() => token.get() !== null);
  const [aviso, setAviso] = useState<string | null>(null);

  const recargar = useCallback(async () => {
    if (!token.get()) {
      setUsuario(null);
      return;
    }
    try {
      setUsuario(await api.get<Usuario>("/auth/me"));
    } catch {
      token.clear();
      setUsuario(null);
    }
  }, []);

  useEffect(() => {
    onSesionExpirada(() => {
      setUsuario(null);
      queryClient.clear();
      setAviso("Tu sesión expiró. Vuelve a iniciar sesión.");
    });
    recargar().finally(() => setCargando(false));
  }, [recargar, queryClient]);

  const entrar = useCallback(async (correo: string, password: string) => {
    const { access_token } = await api.login(correo, password);
    token.set(access_token);
    setAviso(null);
    setUsuario(await api.get<Usuario>("/auth/me"));
  }, []);

  const salir = useCallback(() => {
    token.clear();
    setUsuario(null);
    queryClient.clear();
  }, [queryClient]);

  const valor = useMemo<Sesion>(
    () => ({
      usuario,
      cargando,
      esAdmin: usuario?.rol === "admin" || usuario?.rol === "superusuario",
      esSuperusuario: usuario?.rol === "superusuario",
      aviso,
      entrar,
      salir,
      recargar,
    }),
    [usuario, cargando, aviso, entrar, salir, recargar],
  );

  return <AuthContext value={valor}>{children}</AuthContext>;
}

export function useAuth(): Sesion {
  const ctx = use(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}
