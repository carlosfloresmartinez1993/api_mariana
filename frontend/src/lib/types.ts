// Tipos que reflejan los esquemas Pydantic del backend.
// Los montos llegan como texto ("1234.50") para no perder precisión.

export type Rol = "superusuario" | "admin" | "contador";

export const NOMBRE_ROL: Record<Rol, string> = {
  superusuario: "Superusuario",
  admin: "Administrador",
  contador: "Contador",
};

export interface Pagina<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Usuario {
  id: string;
  nombre: string;
  correo: string;
  rol: Rol;
  activo: boolean;
  fecha_creacion: string;
}

export interface Token {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export const ACCIONES_BITACORA = {
  INICIO_SESION: "Inicio de sesión",
  INICIO_SESION_FALLIDO: "Inicio de sesión fallido",
  CAMBIO_PASSWORD: "Cambio de contraseña",
  CREAR: "Alta",
  EDITAR: "Edición",
  ACTIVAR: "Activación",
  DESACTIVAR: "Desactivación",
  ANULAR: "Anulación",
} as const;

export type AccionBitacora = keyof typeof ACCIONES_BITACORA;

export interface RegistroBitacora {
  id: string;
  fecha: string;
  usuario_id: string | null;
  usuario_nombre: string;
  entidad: string;
  entidad_id: string | null;
  accion: AccionBitacora;
  detalle: Record<string, unknown>;
}
