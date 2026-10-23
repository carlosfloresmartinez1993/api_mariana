import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Exportar, ReporteTabla } from "../components/ReporteTabla";
import { Boton, Campo, Cargando, EncabezadoPagina, ErrorApi, Input, Select, Tarjeta, Vacio } from "../components/ui";
import { api, type Query } from "../lib/api";
import { useFiltros } from "../lib/filtros";
import { useEmpresasCatalogo, useProyectosCatalogo } from "../lib/queries";
import { MONEDAS, type Reporte } from "../lib/types";

type Filtro = "empresa" | "proyecto" | "moneda";

interface Definicion {
  titulo: string;
  descripcion: string;
  ruta: (proyectoId: string) => string;
  fijos?: Query;
  filtros: Filtro[];
  requiereProyecto?: boolean;
  /** Solo usa la fecha «Hasta» (saldo al corte). */
  soloCorte?: boolean;
  /** No usa fechas (p. ej. proyecciones o cuentas pendientes). */
  sinPeriodo?: boolean;
}

const REPORTES: Record<string, Definicion> = {
  "saldos-proyectos": {
    titulo: "Saldo por proyecto",
    descripcion: "Ingresos (neto), gastos, salidas y saldo de cada proyecto, por moneda.",
    ruta: () => "/reportes/saldos-proyectos",
    filtros: ["empresa", "proyecto"],
  },
  "saldos-proyectos-empresa": {
    titulo: "Saldo por proyecto y empresa",
    descripcion: "Cuánto tiene cada proyecto en cada empresa. Un saldo negativo indica que usó dinero de otros proyectos.",
    ruta: () => "/reportes/saldos-proyectos",
    fijos: { por_empresa: true },
    filtros: ["empresa", "proyecto"],
  },
  historial: {
    titulo: "Historial de un proyecto",
    descripcion: "Resumen de ingresos (neto) y egresos del proyecto, con la fecha, empresa y cuenta de cada uno, y el resultado neto.",
    ruta: (p) => `/reportes/historial-proyecto/${p}`,
    filtros: ["proyecto", "empresa"],
    requiereProyecto: true,
  },
  "saldos-cuentas": {
    titulo: "Saldo por cuenta",
    descripcion: "Cuánto hay en cada caja y en cada cuenta de banco, con totales de cajas y bancos por moneda.",
    ruta: () => "/reportes/saldos-cuentas",
    filtros: ["empresa", "moneda"],
  },
  cuadre: {
    titulo: "Cuadre de cuentas y proyectos",
    descripcion: "Por empresa y moneda: entradas − salidas = saldo en cuentas = saldo de los proyectos. Se calcula al corte «Hasta» (por defecto, hoy).",
    ruta: () => "/reportes/cuadre",
    filtros: ["empresa"],
    soloCorte: true,
  },
  "por-categoria": {
    titulo: "Por categoría",
    descripcion: "Entradas (neto) y salidas de cada categoría. Los movimientos sin categoría van al final.",
    ruta: () => "/reportes/por-categoria",
    filtros: ["empresa", "proyecto"],
  },
  "por-proyecto-categoria": {
    titulo: "Por proyecto y categoría",
    descripcion: "En qué categorías entró y salió el dinero de cada proyecto.",
    ruta: () => "/reportes/por-categoria",
    fijos: { por_proyecto: true },
    filtros: ["empresa", "proyecto"],
  },
  "estimado-vs-real": {
    titulo: "Estimado contra real",
    descripcion: "Proyecciones de cada proyecto (ingresos, gastos, trabajadores y fechas) contra lo real, con cuentas por cobrar y por pagar pendientes.",
    ruta: () => "/reportes/estimado-vs-real",
    filtros: ["proyecto"],
    sinPeriodo: true,
  },
  "estimado-vs-real-categoria": {
    titulo: "Estimado contra real por categoría",
    descripcion: "Ingresos y gastos estimados por categoría (partidas de la proyección) contra las entradas (neto) y salidas reales de esa categoría. Solo proyectos con partidas.",
    ruta: () => "/reportes/estimado-vs-real",
    fijos: { por_categoria: true },
    filtros: ["proyecto"],
    sinPeriodo: true,
  },
  "cuentas-por-cobrar-pagar": {
    titulo: "Cuentas por cobrar y por pagar",
    descripcion: "Partidas pendientes de todos los proyectos, con vencimiento. No afectan saldos.",
    ruta: () => "/reportes/cuentas-por-cobrar-pagar",
    filtros: ["proyecto"],
    sinPeriodo: true,
  },
  "gastos-acumulados": {
    titulo: "Gastos acumulados",
    descripcion: "Suma de los porcentajes aplicados en las entradas, por moneda.",
    ruta: () => "/reportes/gastos",
    fijos: { agrupar: "moneda" },
    filtros: ["empresa", "proyecto"],
  },
  "gastos-proyecto": {
    titulo: "Gastos por proyecto",
    descripcion: "Porcentajes aplicados en las entradas de cada proyecto.",
    ruta: () => "/reportes/gastos",
    fijos: { agrupar: "proyecto" },
    filtros: ["empresa", "proyecto"],
  },
  "gastos-empresa": {
    titulo: "Gastos por empresa",
    descripcion: "Porcentajes aplicados en las entradas que llegaron a cada empresa.",
    ruta: () => "/reportes/gastos",
    fijos: { agrupar: "empresa" },
    filtros: ["empresa", "proyecto"],
  },
  "ingresos-proyecto": {
    titulo: "Ingresos por proyecto",
    descripcion: "Lo que llegó a las cuentas (neto) por proyecto.",
    ruta: () => "/reportes/ingresos",
    fijos: { agrupar: "proyecto" },
    filtros: ["empresa", "proyecto"],
  },
  "ingresos-empresa": {
    titulo: "Ingresos por empresa",
    descripcion: "Lo que llegó a las cuentas (neto) de cada empresa.",
    ruta: () => "/reportes/ingresos",
    fijos: { agrupar: "empresa" },
    filtros: ["empresa", "proyecto"],
  },
};

const CLAVES = ["reporte", "desde", "hasta", "empresa_id", "proyecto_id", "moneda"] as const;

export default function Reportes() {
  const { filtros, cambiar } = useFiltros(CLAVES);
  const clave = filtros.reporte in REPORTES ? filtros.reporte : "saldos-proyectos";
  const def = REPORTES[clave];
  const empresas = useEmpresasCatalogo();
  const proyectos = useProyectosCatalogo();

  const query: Query = {
    ...def.fijos,
    desde: def.soloCorte || def.sinPeriodo ? undefined : filtros.desde,
    hasta: def.sinPeriodo ? undefined : filtros.hasta,
    empresa_id: def.filtros.includes("empresa") ? filtros.empresa_id : undefined,
    proyecto_id: def.filtros.includes("proyecto") && !def.requiereProyecto ? filtros.proyecto_id : undefined,
    moneda: def.filtros.includes("moneda") ? filtros.moneda : undefined,
  };
  const listo = !def.requiereProyecto || !!filtros.proyecto_id;
  const ruta = def.ruta(filtros.proyecto_id);

  const reporte = useQuery({
    queryKey: ["reportes", ruta, query],
    queryFn: () => api.get<Reporte>(ruta, query),
    enabled: listo,
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <EncabezadoPagina titulo="Reportes" descripcion="Sin periodo se toma todo el historial. Pesos y dólares siempre por separado." />

      <Tarjeta className="mb-4 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Campo etiqueta="Reporte" className="sm:col-span-2">
            {(id) => (
              <Select id={id} value={clave} onChange={(e) => cambiar({ reporte: e.target.value })}>
                {Object.entries(REPORTES).map(([k, r]) => <option key={k} value={k}>{r.titulo}</option>)}
              </Select>
            )}
          </Campo>
          <Campo etiqueta="Desde">
            {(id) => <Input id={id} type="date" value={def.soloCorte || def.sinPeriodo ? "" : filtros.desde} disabled={def.soloCorte || def.sinPeriodo}
              onChange={(e) => cambiar({ desde: e.target.value })} />}
          </Campo>
          <Campo etiqueta="Hasta">
            {(id) => <Input id={id} type="date" value={def.sinPeriodo ? "" : filtros.hasta} disabled={def.sinPeriodo}
              onChange={(e) => cambiar({ hasta: e.target.value })} />}
          </Campo>
          {def.filtros.includes("proyecto") && (
            <Campo etiqueta={def.requiereProyecto ? "Proyecto *" : "Proyecto"}>
              {(id) => (
                <Select id={id} value={filtros.proyecto_id} onChange={(e) => cambiar({ proyecto_id: e.target.value })}>
                  <option value="">{def.requiereProyecto ? "Elige un proyecto…" : "Todos"}</option>
                  {proyectos.data?.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                </Select>
              )}
            </Campo>
          )}
          {def.filtros.includes("empresa") && (
            <Campo etiqueta="Empresa">
              {(id) => (
                <Select id={id} value={filtros.empresa_id} onChange={(e) => cambiar({ empresa_id: e.target.value })}>
                  <option value="">Todas</option>
                  {empresas.data?.map((e) => <option key={e.id} value={e.id}>{e.nombre}</option>)}
                </Select>
              )}
            </Campo>
          )}
          {def.filtros.includes("moneda") && (
            <Campo etiqueta="Moneda">
              {(id) => (
                <Select id={id} value={filtros.moneda} onChange={(e) => cambiar({ moneda: e.target.value })}>
                  <option value="">Todas</option>
                  {MONEDAS.map((m) => <option key={m} value={m}>{m}</option>)}
                </Select>
              )}
            </Campo>
          )}
          <div className="flex items-end">
            <Boton variante="secundario" className="w-full"
              disabled={!filtros.desde && !filtros.hasta && !filtros.empresa_id && !filtros.proyecto_id && !filtros.moneda}
              onClick={() => cambiar({ desde: "", hasta: "", empresa_id: "", proyecto_id: "", moneda: "" })}>
              Quitar filtros
            </Boton>
          </div>
        </div>
      </Tarjeta>

      <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-black">{reporte.data && listo ? reporte.data.titulo : def.titulo}</h2>
          <p className="text-sm text-neutral-500">{def.descripcion}</p>
        </div>
        {listo && <Exportar ruta={ruta} query={query} nombre={clave} />}
      </div>
      <ErrorApi error={reporte.error} className="mb-4" />
      <Tarjeta>
        {!listo ? (
          <Vacio titulo="Elige un proyecto" descripcion="Este reporte muestra el historial de un solo proyecto." />
        ) : reporte.isLoading || !reporte.data ? (
          <Cargando />
        ) : (
          <ReporteTabla reporte={reporte.data} />
        )}
      </Tarjeta>
    </>
  );
}
