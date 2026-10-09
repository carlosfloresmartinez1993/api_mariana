import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router";
import { useAuth } from "../auth/AuthContext";
import { cn } from "../lib/cn";
import { NOMBRE_ROL } from "../lib/types";
import { Icono, type NombreIcono } from "./Icono";

interface Enlace {
  a: string;
  texto: string;
  icono: NombreIcono;
  soloAdmin?: boolean;
}

const ENLACES: Enlace[] = [
  { a: "/", texto: "Inicio", icono: "inicio" },
  { a: "/usuarios", texto: "Usuarios", icono: "usuarios", soloAdmin: true },
  { a: "/bitacora", texto: "Bitácora", icono: "bitacora", soloAdmin: true },
];

const ENLACE = "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors";
const claseEnlace = ({ isActive }: { isActive: boolean }) =>
  cn(ENLACE, isActive ? "bg-white text-black" : "text-neutral-300 hover:bg-neutral-800 hover:text-white");

function Navegacion({ onNavegar }: { onNavegar?: () => void }) {
  const { usuario, esAdmin, salir } = useAuth();
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-16 shrink-0 items-center gap-2.5 border-b border-neutral-800 px-5">
        <img src="/favicon.svg" alt="" className="size-8" />
        <div className="leading-tight">
          <p className="text-sm font-semibold text-white">Control de Empresas</p>
          <p className="text-xs text-neutral-400">y Proyectos</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {ENLACES.filter((e) => !e.soloAdmin || esAdmin).map((e) => (
          <NavLink key={e.a} to={e.a} end={e.a === "/"} onClick={onNavegar} className={claseEnlace}>
            <Icono nombre={e.icono} />
            {e.texto}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-neutral-800 p-3">
        <div className="px-3 pb-3">
          <p className="truncate text-sm font-medium text-white">{usuario?.nombre}</p>
          <p className="truncate text-xs text-neutral-400">
            {usuario?.correo} · {usuario ? NOMBRE_ROL[usuario.rol] : ""}
          </p>
        </div>
        <NavLink to="/perfil" onClick={onNavegar} className={claseEnlace}>
          <Icono nombre="llave" />
          Cambiar contraseña
        </NavLink>
        <button
          type="button"
          onClick={salir}
          className={cn(ENLACE, "w-full text-neutral-300 hover:bg-neutral-800 hover:text-white")}
        >
          <Icono nombre="salir" />
          Cerrar sesión
        </button>
      </div>
    </div>
  );
}

export function Layout() {
  const [menuAbierto, setMenuAbierto] = useState(false);
  const { pathname } = useLocation();
  const actual = ENLACES.find((e) => (e.a === "/" ? pathname === "/" : pathname.startsWith(e.a)));

  return (
    <div className="min-h-dvh bg-white">
      {/* Menú lateral fijo en escritorio */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 bg-black lg:block">
        <Navegacion />
      </aside>

      {/* Menú deslizable en móvil */}
      {menuAbierto && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMenuAbierto(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 bg-black shadow-xl">
            <Navegacion onNavegar={() => setMenuAbierto(false)} />
          </aside>
        </div>
      )}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-neutral-200 bg-white px-4 lg:hidden">
          <button
            type="button"
            onClick={() => setMenuAbierto(true)}
            className="rounded p-1.5 text-black hover:bg-neutral-100"
            aria-label="Abrir menú"
          >
            <Icono nombre="menu" />
          </button>
          <span className="text-sm font-semibold text-black">{actual?.texto ?? "Control de Empresas y Proyectos"}</span>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
