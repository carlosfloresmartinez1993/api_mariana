// Tipos que reflejan los esquemas Pydantic del backend.
// Los montos llegan como texto ("1234.50") para no perder precisión.

export type Rol = "superusuario" | "admin" | "contador";
export type Moneda = "MXN" | "USD";
export type TipoCuenta = "banco" | "caja";
export type Forma = "transferencia" | "efectivo";
export type Estado = "vigentes" | "anulados" | "todos";

export const MONEDAS: Moneda[] = ["MXN", "USD"];

export const NOMBRE_ROL: Record<Rol, string> = {
  superusuario: "Superusuario",
  admin: "Administrador",
  contador: "Contador",
};

export const NOMBRE_FORMA: Record<Forma, string> = { transferencia: "Transferencia", efectivo: "Efectivo" };
export const NOMBRE_TIPO: Record<TipoCuenta, string> = { banco: "Banco", caja: "Caja" };

/** Efectivo → caja; transferencia → cuenta de banco. */
export const TIPO_DE_FORMA: Record<Forma, TipoCuenta> = { transferencia: "banco", efectivo: "caja" };

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

/** Quién registró el dato y cuándo. */
export interface Registro {
  creado_por: string;
  creado_por_nombre: string;
  fecha_creacion: string;
}

export interface SaldoMoneda {
  moneda: Moneda;
  saldo: string;
}

export interface Empresa extends Registro {
  id: string;
  nombre: string;
  activa: boolean;
  num_cuentas: number;
  num_proyectos: number;
  saldos: SaldoMoneda[];
}

export interface Cuenta extends Registro {
  id: string;
  empresa_id: string;
  empresa_nombre: string;
  tipo: TipoCuenta;
  moneda: Moneda;
  nombre: string;
  banco: string | null;
  numero: string | null;
  activa: boolean;
  saldo: string;
}

export interface SaldoProyecto {
  moneda: Moneda;
  ingresos: string;
  gastos: string;
  salidas: string;
  saldo: string;
}

/** Lo que el proyecto tiene en una empresa (puede ser negativo si usó dinero de otros proyectos). */
export interface SaldoProyectoEmpresa extends SaldoProyecto {
  empresa_id: string;
  empresa_nombre: string;
}

export interface EmpresaBreve {
  id: string;
  nombre: string;
  activa: boolean;
}

export interface Proyecto extends Registro {
  id: string;
  nombre: string;
  descripcion: string | null;
  activo: boolean;
  empresas: EmpresaBreve[];
  // Proyecciones (opcionales; no afectan saldos)
  estimado_ingresos_mxn: string | null;
  estimado_gastos_mxn: string | null;
  estimado_ingresos_usd: string | null;
  estimado_gastos_usd: string | null;
  trabajadores_estimados: number | null;
  fecha_inicio_estimada: string | null;
  fecha_fin_estimada: string | null;
  /** Todas las empresas. */
  saldos: SaldoProyecto[];
  saldos_por_empresa: SaldoProyectoEmpresa[];
}

/** Factura opcional de una entrada o salida. */
interface Factura {
  requiere_factura: boolean;
  factura_nombre: string | null;
  factura_tipo: string | null;
  factura_tamano: number | null;
  factura_subida_en: string | null;
}

interface Anulacion {
  anulado: boolean;
  motivo_anulacion: string | null;
  anulado_por: string | null;
  fecha_anulacion: string | null;
}

export interface Entrada extends Registro, Anulacion, Factura {
  id: string;
  categoria_id: string | null;
  categoria_nombre: string | null;
  proyecto_id: string;
  proyecto_nombre: string;
  empresa_id: string;
  empresa_nombre: string;
  cuenta_id: string;
  cuenta_nombre: string;
  moneda: Moneda;
  fecha: string;
  forma: Forma;
  monto: string;
  porcentaje_gasto: string;
  monto_gasto: string;
  monto_neto: string;
  concepto: string | null;
  referencia: string | null;
}

export interface Salida extends Registro, Anulacion, Factura {
  id: string;
  categoria_id: string | null;
  categoria_nombre: string | null;
  proyecto_id: string;
  proyecto_nombre: string;
  empresa_id: string;
  empresa_nombre: string;
  cuenta_id: string;
  cuenta_nombre: string;
  moneda: Moneda;
  fecha: string;
  forma: Forma;
  monto: string;
  concepto: string;
  beneficiario: string | null;
}

export type Movimiento = Entrada | Salida;

export interface Categoria extends Registro {
  id: string;
  nombre: string;
  descripcion: string | null;
  activa: boolean;
}

export type TipoPendiente = "por_cobrar" | "por_pagar";
export const NOMBRE_TIPO_PENDIENTE: Record<TipoPendiente, string> = { por_cobrar: "Por cobrar", por_pagar: "Por pagar" };

/** Cuenta por cobrar o por pagar de un proyecto. No afecta saldos. */
export interface Pendiente extends Registro {
  id: string;
  proyecto_id: string;
  proyecto_nombre: string;
  tipo: TipoPendiente;
  concepto: string;
  contraparte: string | null;
  moneda: Moneda;
  monto: string;
  fecha_vencimiento: string | null;
  liquidada: boolean;
  fecha_liquidacion: string | null;
  nota: string | null;
  vencida: boolean;
}

export interface Reporte {
  titulo: string;
  parametros: Record<string, unknown>;
  columnas: { clave: string; etiqueta: string }[];
  filas: Record<string, unknown>[];
  totales: Record<string, unknown>[];
  elaborado_por: string | null;
  /** "tabla" o "resumen" (estado de ingresos y egresos: cada fila trae su `estilo`). */
  estilo: "tabla" | "resumen";
}

export interface Resumen {
  dinero: { moneda: Moneda; cajas: string; bancos: string; total: string }[];
  empresas: number;
  proyectos: number;
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
  VINCULAR: "Vinculación",
  DESVINCULAR: "Desvinculación",
  CAMBIO_SALDO_INICIAL: "Cambio de saldo inicial",
  SUBIR_FACTURA: "Factura adjunta",
  ELIMINAR_FACTURA: "Factura eliminada",
  LIQUIDAR: "Liquidación",
  ELIMINAR: "Eliminación",
} as const;

export type AccionBitacora = keyof typeof ACCIONES_BITACORA;

export const ENTIDADES_BITACORA = ["Usuario", "Empresa", "Cuenta", "Proyecto", "Entrada", "Salida", "Categoría", "Pendiente"] as const;

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
