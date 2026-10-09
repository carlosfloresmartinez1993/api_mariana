import {
  useEffect,
  useId,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { cn } from "../lib/cn";

// Interfaz en blanco y negro: el énfasis se logra con negro sólido, bordes y peso de la letra.

// ------------------------------------------------------------------ botones
type Variante = "primario" | "secundario" | "peligro" | "fantasma";

const VARIANTES: Record<Variante, string> = {
  primario: "bg-black text-white hover:bg-neutral-800 focus-visible:outline-black",
  secundario: "bg-white text-black ring-1 ring-inset ring-black hover:bg-neutral-100 focus-visible:outline-black",
  peligro: "bg-white text-black ring-2 ring-inset ring-black hover:bg-black hover:text-white focus-visible:outline-black",
  fantasma: "text-neutral-600 hover:bg-neutral-100 hover:text-black focus-visible:outline-neutral-400",
};

interface BotonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante;
  tamano?: "sm" | "md";
  cargando?: boolean;
}

export function Boton({
  variante = "primario",
  tamano = "md",
  cargando = false,
  disabled,
  className,
  children,
  type = "button",
  ...props
}: BotonProps) {
  return (
    <button
      type={type}
      disabled={disabled || cargando}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        tamano === "sm" ? "px-2.5 py-1.5 text-xs" : "px-3.5 py-2 text-sm",
        VARIANTES[variante],
        className,
      )}
      {...props}
    >
      {cargando && <Spinner className="size-4" />}
      {children}
    </button>
  );
}

// ------------------------------------------------------------------ campos
const CAMPO =
  "block w-full rounded-md border-0 bg-white px-3 py-2 text-sm text-black ring-1 ring-inset " +
  "ring-neutral-300 placeholder:text-neutral-400 focus:ring-2 focus:ring-inset focus:ring-black " +
  "disabled:bg-neutral-50 disabled:text-neutral-500";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(CAMPO, className)} {...props} />;
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea rows={3} className={cn(CAMPO, className)} {...props} />;
}

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(CAMPO, "pr-8", className)} {...props}>
      {children}
    </select>
  );
}

interface CampoProps {
  etiqueta: string;
  ayuda?: ReactNode;
  requerido?: boolean;
  className?: string;
  children: (id: string) => ReactNode;
}

/** Envuelve un control con su etiqueta; `children` recibe el id para enlazarlos. */
export function Campo({ etiqueta, ayuda, requerido, className, children }: CampoProps) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-neutral-800">
        {etiqueta}
        {requerido && <span className="ml-0.5">*</span>}
      </label>
      {children(id)}
      {ayuda && <p className="mt-1 text-xs text-neutral-500">{ayuda}</p>}
    </div>
  );
}

// ------------------------------------------------------------------ estructura
export function Tarjeta({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("rounded-lg bg-white ring-1 ring-neutral-200", className)}>{children}</div>;
}

export function EncabezadoPagina({
  titulo,
  descripcion,
  acciones,
}: {
  titulo: ReactNode;
  descripcion?: ReactNode;
  acciones?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-black">{titulo}</h1>
        {descripcion && <p className="mt-1 text-sm text-neutral-500">{descripcion}</p>}
      </div>
      {acciones && <div className="flex shrink-0 flex-wrap gap-2">{acciones}</div>}
    </div>
  );
}

type Tono = "neutro" | "fuerte" | "tenue";

const TONOS_INSIGNIA: Record<Tono, string> = {
  neutro: "bg-white text-neutral-800 ring-neutral-300",
  fuerte: "bg-black text-white ring-black",
  tenue: "bg-neutral-100 text-neutral-500 ring-neutral-200",
};

export function Insignia({ tono = "neutro", children }: { tono?: Tono; children: ReactNode }) {
  return (
    <span className={cn("inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ring-1 ring-inset", TONOS_INSIGNIA[tono])}>
      {children}
    </span>
  );
}

type TonoAviso = "info" | "aviso" | "peligro";

export function Aviso({
  tono = "info",
  titulo,
  children,
  className,
}: {
  tono?: TonoAviso;
  titulo?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div
      role={tono === "peligro" ? "alert" : "status"}
      className={cn(
        "rounded-md p-3 text-sm",
        tono === "info" && "bg-neutral-50 text-neutral-800 ring-1 ring-neutral-200",
        tono === "aviso" && "bg-white text-black ring-1 ring-black",
        tono === "peligro" && "bg-white font-medium text-black ring-2 ring-black",
        className,
      )}
    >
      {titulo && <p className="font-semibold">{titulo}</p>}
      {children && <div className={titulo ? "mt-1" : undefined}>{children}</div>}
    </div>
  );
}

export function ErrorApi({ error, className }: { error: unknown; className?: string }) {
  if (!error) return null;
  const mensaje = error instanceof Error ? error.message : "Ocurrió un error";
  return (
    <Aviso tono="peligro" className={className}>
      {mensaje}
    </Aviso>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={cn("animate-spin", className ?? "size-5")} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25" />
      <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" strokeWidth="4" className="opacity-75" />
    </svg>
  );
}

export function Cargando({ texto = "Cargando…" }: { texto?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-12 text-sm text-neutral-500">
      <Spinner />
      {texto}
    </div>
  );
}

export function Vacio({ titulo, descripcion, accion }: { titulo: string; descripcion?: string; accion?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <p className="text-sm font-medium text-black">{titulo}</p>
      {descripcion && <p className="mt-1 max-w-sm text-sm text-neutral-500">{descripcion}</p>}
      {accion && <div className="mt-4">{accion}</div>}
    </div>
  );
}

// ------------------------------------------------------------------ tablas
export function Tabla({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-neutral-200 text-sm">{children}</table>
    </div>
  );
}

export function Th({ children, derecha, className }: { children?: ReactNode; derecha?: boolean; className?: string }) {
  return (
    <th
      scope="col"
      className={cn(
        "whitespace-nowrap bg-neutral-50 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-neutral-600",
        derecha ? "text-right" : "text-left",
        className,
      )}
    >
      {children}
    </th>
  );
}

export function Td({ children, derecha, className }: { children?: ReactNode; derecha?: boolean; className?: string }) {
  return <td className={cn("px-4 py-3 text-neutral-800", derecha && "text-right tabular-nums", className)}>{children}</td>;
}

export function Paginacion({
  total,
  limit,
  offset,
  onCambiar,
}: {
  total: number;
  limit: number;
  offset: number;
  onCambiar: (offset: number) => void;
}) {
  if (total <= limit) {
    return total > 0 ? (
      <div className="border-t border-neutral-200 px-4 py-3 text-xs text-neutral-500">{total} registro(s)</div>
    ) : null;
  }
  const desde = offset + 1;
  const hasta = Math.min(offset + limit, total);
  return (
    <div className="flex items-center justify-between border-t border-neutral-200 px-4 py-3">
      <p className="text-xs text-neutral-500">
        {desde}–{hasta} de {total}
      </p>
      <div className="flex gap-2">
        <Boton variante="secundario" tamano="sm" disabled={offset === 0} onClick={() => onCambiar(Math.max(0, offset - limit))}>
          Anterior
        </Boton>
        <Boton variante="secundario" tamano="sm" disabled={hasta >= total} onClick={() => onCambiar(offset + limit)}>
          Siguiente
        </Boton>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ modal
export function Modal({
  abierto,
  titulo,
  descripcion,
  onCerrar,
  children,
  ancho = "md",
}: {
  abierto: boolean;
  titulo: ReactNode;
  descripcion?: ReactNode;
  onCerrar: () => void;
  children: ReactNode;
  ancho?: "md" | "lg" | "xl";
}) {
  useEffect(() => {
    if (!abierto) return;
    const alTeclear = (e: KeyboardEvent) => e.key === "Escape" && onCerrar();
    document.addEventListener("keydown", alTeclear);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", alTeclear);
      document.body.style.overflow = "";
    };
  }, [abierto, onCerrar]);

  if (!abierto) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/50" onClick={onCerrar} />
      <div
        className={cn(
          "relative max-h-[90vh] w-full overflow-y-auto rounded-lg bg-white shadow-xl ring-1 ring-black",
          { md: "max-w-lg", lg: "max-w-2xl", xl: "max-w-4xl" }[ancho],
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-neutral-200 px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-black">{titulo}</h2>
            {descripcion && <p className="mt-0.5 text-sm text-neutral-500">{descripcion}</p>}
          </div>
          <button
            type="button"
            onClick={onCerrar}
            className="rounded p-1 text-neutral-500 hover:bg-neutral-100 hover:text-black"
            aria-label="Cerrar"
          >
            <svg className="size-5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
            </svg>
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  );
}

export function PieModal({ children }: { children: ReactNode }) {
  return <div className="-mx-5 -mb-4 mt-5 flex justify-end gap-2 border-t border-neutral-200 bg-neutral-50 px-5 py-3">{children}</div>;
}
