import { useState, type ReactNode } from "react";
import { Link } from "react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { Anular } from "../components/formularios/Anular";
import { EntradaForm, SalidaForm } from "../components/formularios/MovimientoForms";
import { Icono } from "../components/Icono";
import {
  Boton,
  Campo,
  Cargando,
  EncabezadoPagina,
  ErrorApi,
  Input,
  Insignia,
  Monto,
  Paginacion,
  Select,
  Tabla,
  Tarjeta,
  Td,
  Th,
  Vacio,
} from "../components/ui";
import { api } from "../lib/api";
import { dinero, fecha, porcentaje } from "../lib/format";
import { useFiltros } from "../lib/filtros";
import { useCuentas, useEmpresasCatalogo, useProyectosCatalogo } from "../lib/queries";
import { MONEDAS, NOMBRE_FORMA, type Entrada, type Movimiento, type Pagina, type Salida } from "../lib/types";

const LIMITE = 50;
const CLAVES = ["proyecto_id", "empresa_id", "cuenta_id", "moneda", "forma", "desde", "hasta", "estado", "q"] as const;
type Filtros = Record<(typeof CLAVES)[number], string>;

function useMovimientos<T>(ruta: string) {
  const f = useFiltros(CLAVES);
  const query = useQuery({
    queryKey: [ruta.slice(1), "lista", f.filtros, f.offset],
    queryFn: () => api.get<Pagina<T>>(ruta, { ...f.filtros, limit: LIMITE, offset: f.offset }),
    placeholderData: keepPreviousData,
  });
  return { ...f, ...query };
}

/** Barra de filtros común de entradas y salidas. */
function BarraFiltros({ filtros, cambiar, limpiar, activos }: {
  filtros: Filtros;
  cambiar: (c: Partial<Filtros>) => void;
  limpiar: () => void;
  activos: boolean;
}) {
  const proyectos = useProyectosCatalogo();
  const empresas = useEmpresasCatalogo();
  const cuentas = useCuentas();
  const cuenta = cuentas.data?.find((c) => c.id === filtros.cuenta_id);
  return (
    <Tarjeta className="mb-4 p-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Campo etiqueta="Proyecto">
          {(id) => (
            <Select id={id} value={filtros.proyecto_id} onChange={(e) => cambiar({ proyecto_id: e.target.value })}>
              <option value="">Todos</option>
              {proyectos.data?.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
            </Select>
          )}
        </Campo>
        <Campo etiqueta="Empresa">
          {(id) => (
            <Select id={id} value={filtros.empresa_id} onChange={(e) => cambiar({ empresa_id: e.target.value, cuenta_id: "" })}>
              <option value="">Todas</option>
              {empresas.data?.map((e) => <option key={e.id} value={e.id}>{e.nombre}</option>)}
            </Select>
          )}
        </Campo>
        <Campo etiqueta="Cuenta">
          {(id) => (
            <Select id={id} value={filtros.cuenta_id} onChange={(e) => cambiar({ cuenta_id: e.target.value })}>
              <option value="">Todas</option>
              {cuentas.data?.filter((c) => !filtros.empresa_id || c.empresa_id === filtros.empresa_id).map((c) => (
                <option key={c.id} value={c.id}>{c.empresa_nombre} · {c.nombre}</option>
              ))}
            </Select>
          )}
        </Campo>
        <Campo etiqueta="Moneda">
          {(id) => (
            <Select id={id} value={filtros.moneda} onChange={(e) => cambiar({ moneda: e.target.value })}>
              <option value="">Todas</option>
              {MONEDAS.map((m) => <option key={m} value={m}>{m}</option>)}
            </Select>
          )}
        </Campo>
        <Campo etiqueta="Forma">
          {(id) => (
            <Select id={id} value={filtros.forma} onChange={(e) => cambiar({ forma: e.target.value })}>
              <option value="">Todas</option>
              <option value="transferencia">Transferencia</option>
              <option value="efectivo">Efectivo</option>
            </Select>
          )}
        </Campo>
        <Campo etiqueta="Desde">
          {(id) => <Input id={id} type="date" value={filtros.desde} onChange={(e) => cambiar({ desde: e.target.value })} />}
        </Campo>
        <Campo etiqueta="Hasta">
          {(id) => <Input id={id} type="date" value={filtros.hasta} onChange={(e) => cambiar({ hasta: e.target.value })} />}
        </Campo>
        <Campo etiqueta="Estado">
          {(id) => (
            <Select id={id} value={filtros.estado} onChange={(e) => cambiar({ estado: e.target.value })}>
              <option value="">Vigentes</option>
              <option value="anulados">Anulados</option>
              <option value="todos">Todos</option>
            </Select>
          )}
        </Campo>
        <Campo etiqueta="Buscar texto">
          {(id) => <Input id={id} type="search" value={filtros.q} onChange={(e) => cambiar({ q: e.target.value })} placeholder="Concepto, referencia…" />}
        </Campo>
        <div className="flex items-end">
          <Boton variante="secundario" disabled={!activos} onClick={limpiar} className="w-full">Quitar filtros</Boton>
        </div>
      </div>
      {cuenta && <p className="mt-3 text-xs text-neutral-500">Saldo actual de {cuenta.nombre}: {dinero(cuenta.saldo, cuenta.moneda)}</p>}
    </Tarjeta>
  );
}

/** Acciones de una fila: editar y anular, solo si el usuario puede corregir el movimiento. */
function Acciones({ mov, onEditar, onAnular }: { mov: Movimiento; onEditar: () => void; onAnular: () => void }) {
  const { puedeCorregir } = useAuth();
  if (mov.anulado || !puedeCorregir(mov)) return null;
  return (
    <>
      <Boton variante="fantasma" tamano="sm" onClick={onEditar}>Editar</Boton>
      <Boton variante="fantasma" tamano="sm" onClick={onAnular}>Anular</Boton>
    </>
  );
}

function Registrado({ mov }: { mov: Movimiento }) {
  return (
    <>
      <p>{mov.creado_por_nombre}</p>
      {mov.anulado && (
        <p className="text-xs"><Insignia tono="tenue">Anulado</Insignia> <span title={mov.motivo_anulacion ?? ""}>{mov.motivo_anulacion}</span></p>
      )}
    </>
  );
}

function Contenido<T extends Movimiento>({ isLoading, data, offset, cambiar, vacio, cabecera, fila }: {
  isLoading: boolean;
  data: Pagina<T> | undefined;
  offset: number;
  cambiar: (c: { offset: number }) => void;
  vacio: ReactNode;
  cabecera: ReactNode;
  fila: (m: T) => ReactNode;
}) {
  if (isLoading) return <Cargando />;
  if (!data?.items.length) return <>{vacio}</>;
  return (
    <>
      <Tabla>
        <thead><tr>{cabecera}</tr></thead>
        <tbody className="divide-y divide-neutral-100">
          {data.items.map((m) => (
            <tr key={m.id} className={m.anulado ? "text-neutral-400 line-through decoration-neutral-300" : "hover:bg-neutral-50"}>{fila(m)}</tr>
          ))}
        </tbody>
      </Tabla>
      <Paginacion total={data.total} limit={LIMITE} offset={offset} onCambiar={(o) => cambiar({ offset: o })} />
    </>
  );
}

// ------------------------------------------------------------------ entradas
export function Entradas() {
  const m = useMovimientos<Entrada>("/entradas");
  const [form, setForm] = useState<{ entrada: Entrada | null } | null>(null);
  const [anulando, setAnulando] = useState<Entrada | null>(null);

  return (
    <>
      <EncabezadoPagina titulo="Entradas" descripcion="Dinero que entra a un proyecto. El % de gasto se lo queda el proveedor: a la cuenta llega el neto."
        acciones={<Boton onClick={() => setForm({ entrada: null })}><Icono nombre="mas" className="size-4" /> Nueva entrada</Boton>} />
      <BarraFiltros {...m} />
      <ErrorApi error={m.error} className="mb-4" />
      <Tarjeta>
        <Contenido {...m} vacio={<Vacio titulo="Sin entradas" descripcion={m.activos ? "No hay entradas con esos filtros." : undefined} />}
          cabecera={<>
            <Th>Fecha</Th><Th>Proyecto</Th><Th>Empresa · cuenta</Th><Th>Forma</Th>
            <Th derecha>Recibido</Th><Th derecha>% gasto</Th><Th derecha>Gasto</Th><Th derecha>Neto</Th>
            <Th>Concepto</Th><Th>Registró</Th><Th><span className="sr-only">Acciones</span></Th>
          </>}
          fila={(e) => <>
            <Td className="whitespace-nowrap">{fecha(e.fecha)}</Td>
            <Td><Link to={`/proyectos/${e.proyecto_id}`} className="font-medium hover:underline">{e.proyecto_nombre}</Link></Td>
            <Td>{e.empresa_nombre}<p className="text-xs text-neutral-500">{e.cuenta_nombre}</p></Td>
            <Td>{NOMBRE_FORMA[e.forma]}</Td>
            <Td derecha><Monto valor={e.monto} moneda={e.moneda} /></Td>
            <Td derecha>{Number(e.porcentaje_gasto) ? porcentaje(e.porcentaje_gasto) : "—"}</Td>
            <Td derecha>{Number(e.monto_gasto) ? <Monto valor={e.monto_gasto} /> : "—"}</Td>
            <Td derecha className="font-semibold"><Monto valor={e.monto_neto} /></Td>
            <Td className="max-w-48">{e.concepto}{e.referencia && <p className="text-xs text-neutral-500">Ref. {e.referencia}</p>}</Td>
            <Td className="text-neutral-500"><Registrado mov={e} /></Td>
            <Td className="whitespace-nowrap text-right"><Acciones mov={e} onEditar={() => setForm({ entrada: e })} onAnular={() => setAnulando(e)} /></Td>
          </>}
        />
      </Tarjeta>
      <EntradaForm abierto={form !== null} entrada={form?.entrada} onCerrar={() => setForm(null)} />
      <Anular ruta={anulando ? `/entradas/${anulando.id}` : null} titulo="Anular entrada" onCerrar={() => setAnulando(null)}
        resumen={anulando && <>{fecha(anulando.fecha)} · {anulando.proyecto_nombre} · {anulando.cuenta_nombre} · neto {dinero(anulando.monto_neto, anulando.moneda)}</>} />
    </>
  );
}

// ------------------------------------------------------------------ salidas
export function Salidas() {
  const m = useMovimientos<Salida>("/salidas");
  const [form, setForm] = useState<{ salida: Salida | null } | null>(null);
  const [anulando, setAnulando] = useState<Salida | null>(null);

  return (
    <>
      <EncabezadoPagina titulo="Salidas" descripcion="Dinero que sale de un proyecto, desde una cuenta de una empresa."
        acciones={<Boton onClick={() => setForm({ salida: null })}><Icono nombre="mas" className="size-4" /> Nueva salida</Boton>} />
      <BarraFiltros {...m} />
      <ErrorApi error={m.error} className="mb-4" />
      <Tarjeta>
        <Contenido {...m} vacio={<Vacio titulo="Sin salidas" descripcion={m.activos ? "No hay salidas con esos filtros." : undefined} />}
          cabecera={<>
            <Th>Fecha</Th><Th>Proyecto</Th><Th>Empresa · cuenta</Th><Th>Forma</Th><Th derecha>Monto</Th>
            <Th>Concepto</Th><Th>Registró</Th><Th><span className="sr-only">Acciones</span></Th>
          </>}
          fila={(s) => <>
            <Td className="whitespace-nowrap">{fecha(s.fecha)}</Td>
            <Td><Link to={`/proyectos/${s.proyecto_id}`} className="font-medium hover:underline">{s.proyecto_nombre}</Link></Td>
            <Td>{s.empresa_nombre}<p className="text-xs text-neutral-500">{s.cuenta_nombre}</p></Td>
            <Td>{NOMBRE_FORMA[s.forma]}</Td>
            <Td derecha className="font-semibold"><Monto valor={s.monto} moneda={s.moneda} /></Td>
            <Td className="max-w-56">{s.concepto}{s.beneficiario && <p className="text-xs text-neutral-500">{s.beneficiario}</p>}</Td>
            <Td className="text-neutral-500"><Registrado mov={s} /></Td>
            <Td className="whitespace-nowrap text-right"><Acciones mov={s} onEditar={() => setForm({ salida: s })} onAnular={() => setAnulando(s)} /></Td>
          </>}
        />
      </Tarjeta>
      <SalidaForm abierto={form !== null} salida={form?.salida} onCerrar={() => setForm(null)} />
      <Anular ruta={anulando ? `/salidas/${anulando.id}` : null} titulo="Anular salida" onCerrar={() => setAnulando(null)}
        resumen={anulando && <>{fecha(anulando.fecha)} · {anulando.proyecto_nombre} · {anulando.concepto} · {dinero(anulando.monto, anulando.moneda)}</>} />
    </>
  );
}
