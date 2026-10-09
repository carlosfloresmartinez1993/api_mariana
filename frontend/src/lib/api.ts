const BASE = (import.meta.env.VITE_API_URL ?? "/api").replace(/\/$/, "");
const CLAVE_TOKEN = "cep_token";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, mensaje: string) {
    super(mensaje);
    this.status = status;
  }
}

// ------------------------------------------------------------------ token
let alExpirar: (() => void) | null = null;

export const token = {
  get: (): string | null => {
    try {
      return localStorage.getItem(CLAVE_TOKEN);
    } catch {
      return null;
    }
  },
  set: (valor: string) => {
    try {
      localStorage.setItem(CLAVE_TOKEN, valor);
    } catch {
      /* almacenamiento no disponible */
    }
  },
  clear: () => {
    try {
      localStorage.removeItem(CLAVE_TOKEN);
    } catch {
      /* almacenamiento no disponible */
    }
  },
};

/** Se llama cuando el backend responde 401 (token vencido o usuario desactivado). */
export function onSesionExpirada(fn: () => void) {
  alExpirar = fn;
}

// ---------------------------------------------------------------- errores
interface ErrorValidacion {
  loc?: (string | number)[];
  msg?: string;
}

function mensajeDeError(status: number, cuerpo: unknown): string {
  if (cuerpo && typeof cuerpo === "object") {
    const { detail, error } = cuerpo as { detail?: unknown; error?: unknown };
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      // Errores de validación de FastAPI: [{loc: ["body", "monto"], msg: "..."}]
      return (detail as ErrorValidacion[])
        .map((e) => {
          const campo = e.loc?.filter((p) => p !== "body" && p !== "query").join(".");
          const msg = (e.msg ?? "valor inválido").replace(/^Value error, /, "");
          return campo ? `${campo}: ${msg}` : msg;
        })
        .join(" · ");
    }
    if (typeof error === "string") {
      return status === 429 ? "Demasiados intentos. Espera un minuto e inténtalo de nuevo." : error;
    }
  }
  if (status === 429) return "Demasiados intentos. Espera un minuto e inténtalo de nuevo.";
  if (status >= 500) return "Error interno del servidor";
  return `Error ${status}`;
}

// ---------------------------------------------------------------- peticiones
/** Un arreglo se envía como parámetro repetido: ?empresa_id=a&empresa_id=b */
export type Query = Record<string, string | number | boolean | null | undefined | string[]>;

export function construirUrl(ruta: string, query?: Query): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query ?? {})) {
    if (Array.isArray(v)) v.forEach((x) => params.append(k, x));
    else if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  }
  const qs = params.toString();
  return `${BASE}${ruta}${qs ? `?${qs}` : ""}`;
}

interface Opciones {
  method?: string;
  query?: Query;
  json?: unknown;
  body?: BodyInit;
}

async function peticion(ruta: string, { method = "GET", query, json, body }: Opciones = {}): Promise<Response> {
  const headers: Record<string, string> = {};
  const t = token.get();
  if (t) headers.Authorization = `Bearer ${t}`;
  if (json !== undefined) headers["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(construirUrl(ruta, query), {
      method,
      headers,
      body: json !== undefined ? JSON.stringify(json) : body,
    });
  } catch {
    throw new ApiError(0, "No se pudo conectar con el servidor");
  }

  if (!res.ok) {
    const cuerpo = await res.json().catch(() => null);
    if (res.status === 401 && t && ruta !== "/auth/login") {
      token.clear();
      alExpirar?.();
    }
    throw new ApiError(res.status, mensajeDeError(res.status, cuerpo));
  }
  return res;
}

async function comoJson<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(ruta: string, query?: Query) => peticion(ruta, { query }).then(comoJson<T>),
  post: <T>(ruta: string, json?: unknown, query?: Query) =>
    peticion(ruta, { method: "POST", json, query }).then(comoJson<T>),
  patch: <T>(ruta: string, json: unknown) => peticion(ruta, { method: "PATCH", json }).then(comoJson<T>),
  delete: (ruta: string, query?: Query) => peticion(ruta, { method: "DELETE", query }).then(comoJson<void>),
  put: <T>(ruta: string, body: BodyInit) => peticion(ruta, { method: "PUT", body }).then(comoJson<T>),

  /** Login OAuth2: el backend espera un formulario con username/password. */
  login: (correo: string, password: string) =>
    peticion("/auth/login", {
      method: "POST",
      body: new URLSearchParams({ username: correo, password }),
    }).then(comoJson<{ access_token: string; expires_in: number }>),

  /** Descarga un recurso protegido como Blob (archivos y reportes exportados). */
  blob: (ruta: string, query?: Query) => peticion(ruta, { query }).then((r) => r.blob()),
};

/** Dispara la descarga de un Blob en el navegador. */
export function guardarBlob(blob: Blob, nombre: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
