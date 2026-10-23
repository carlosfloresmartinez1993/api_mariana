import { useState } from "react";
import { Link, useParams } from "react-router";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { CargaMasiva } from "../components/CargaMasiva";
import { EntradaForm, SalidaForm } from "../components/formularios/MovimientoForms";
import { ProyectoForm } from "../components/formularios/NombreForm";
import { Icono } from "../components/Icono";
import { PartidasProyecto } from "../components/PartidasEstimadas";
import { PendientesProyecto, ProyeccionVsReal } from "../components/Pendientes";
import { Exportar, ReporteTabla } from "../components/ReporteTabla";
import { useToast } from "../components/Toast";
import {
  Aviso,
  Boton,
  Campo,
  Cargando,
  EncabezadoPagina,
  ErrorApi,
  Input,
  Insignia,
  Monto,
  Select,
  Tabla,
  Tarjeta,
  Td,
  Th,
} from "../components/ui";
import { api } from "../lib/api";
import { fecha } from "../lib/format";
import { useFiltros } from "../lib/filtros";
import { useEmpresasCatalogo } from "../lib/queries";
import type { Proyecto, Reporte } from "../lib/types";

const CLAVES = ["desde", "hasta", "empresa_id"] as const;

export default function ProyectoDetalle() {
  const { id = "" } = useParams();
  const { puedeCorregir } = useAuth();
  const avisar = useToast();
  const qc = useQueryClient();
  const { filtros, cambiar, limpiar, activos } = useFiltros(CLAVES);
  const [editando, setEditando] = useState(false);
  const [movimiento, setMovimiento] = useState<"entrada" | "salida" | null>(null);
  const [vincular, setVincular] = useState("");
  const [carga, setCarga] = useState(false);
  const empresas = useEmpresasCatalogo();

  const proyecto = useQuery({ queryKey: ["proyectos", id], queryFn: () => api.get<Proyecto>(`/proyectos/${id}`) });
  const historial = useQuery({
    queryKey: ["reportes", "historial", id, filtros],
    queryFn: () => api.get<Reporte>(`/reportes/historial-proyecto/${id}`, filtros),
    placeholderData: keepPreviousData,
  });

  if (proyecto.isLoading) return <Cargando />;
  if (proyecto.error || !proyecto.data) return <ErrorApi error={proyecto.error} />;
  const p = proyecto.data;
  const corregible = puedeCorregir(p);
  const sinVincular = (empresas.data ?? []).filter((e) => e.activa && !p.empresas.some((x) => x.id === e.id));

  async function accion(fn: () => Promise<unknown>, mensaje: string) {
    try {
      await fn();
      await qc.invalidateQueries({ queryKey: ["proyectos"] });
      await qc.invalidateQueries({ queryKey: ["empresas"] });
      avisar(mensaje);
    } catch (err) {
      avisar((err as Error).message, "error");
    }
  }

  return (
    <>
      <Link to="/proyectos" className="mb-3 inline-flex items-center gap-1 text-sm text-neutral-600 hover:text-black">
        <Icono nombre="flecha" className="size-4" /> Proyectos
      </Link>
      <EncabezadoPagina
        titulo={<>{p.nombre} {!p.activo && <Insignia tono="tenue">Desactivado</Insignia>}</>}
        descripcion={p.descripcion || `Registrado por ${p.creado_por_nombre} el ${fecha(p.fecha_creacion)}`}
        acciones={
          <>
            {p.activo && <Boton onClick={() => setMovimiento("entrada")}><Icono nombre="entradas" className="size-4" /> Entrada</Boton>}
            {p.activo && <Boton variante="secundario" onClick={() => setMovimiento("salida")}><Icono nombre="salidas" className="size-4" /> Salida</Boton>}
            {p.activo && <Boton variante="secundario" onClick={() => setCarga(true)}><Icono nombre="subir" className="size-4" /> Carga masiva</Boton>}
            {corregible && <Boton variante="secundario" onClick={() => setEditando(true)}>Editar</Boton>}
            {corregible && (
              <Boton variante="secundario" onClick={() => accion(() => api.post(`/proyectos/${p.id}/${p.activo ? "desactivar" : "activar"}`),
                p.activo ? "Proyecto desactivado" : "Proyecto activado")}>
                {p.activo ? "Desactivar" : "Activar"}
              </Boton>
            )}
          </>
        }
      />

      {p.activo && p.saldos.length === 0 && (
        <Aviso className="mb-6" titulo="El proyecto aún no tiene movimientos">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <span>Si ya los tienes en Excel (FECHA, CONCEPTO, CARGO, ABONO), puedes cargarlos todos de una vez.</span>
            <Boton tamano="sm" onClick={() => setCarga(true)}><Icono nombre="subir" className="size-4" /> Carga masiva desde Excel</Boton>
          </div>
        </Aviso>
      )}

      {p.saldos.length > 0 && (
        <div className="mb-6 grid gap-4 md:grid-cols-2">
          {p.saldos.map((s) => (
            <Tarjeta key={s.moneda} className="p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Saldo en {s.moneda}</p>
              <p className="mt-1 text-2xl font-semibold text-black"><Monto valor={s.saldo} moneda={s.moneda} /></p>
              <div className="mt-3 grid grid-cols-3 gap-3 border-t border-neutral-200 pt-3 text-sm">
                <div><p className="text-neutral-500">Ingresos (neto)</p><Monto valor={s.ingresos} /></div>
                <div><p className="text-neutral-500">Gastos</p><Monto valor={s.gastos} /></div>
                <div><p className="text-neutral-500">Salidas</p><Monto valor={s.salidas} /></div>
              </div>
            </Tarjeta>
          ))}
        </div>
      )}

      <ProyeccionVsReal proyecto={p} />
      <PartidasProyecto proyecto={p} />

      {p.saldos_por_empresa.length > 0 && (
        <>
          <h2 className="mb-1 text-lg font-semibold text-black">Saldo por empresa</h2>
          <p className="mb-3 text-sm text-neutral-500">Cuánto tiene el proyecto en cada empresa. Si es negativo, usó dinero de otros proyectos.</p>
          <Tarjeta className="mb-6">
            <Tabla>
              <thead>
                <tr>
                  <Th>Empresa</Th>
                  <Th>Moneda</Th>
                  <Th derecha>Ingresos (neto)</Th>
                  <Th derecha>Gastos</Th>
                  <Th derecha>Salidas</Th>
                  <Th derecha>Saldo</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {p.saldos_por_empresa.map((s) => (
                  <tr key={`${s.empresa_id}-${s.moneda}`} className="hover:bg-neutral-50">
                    <Td><Link to={`/empresas/${s.empresa_id}`} className="font-medium text-black hover:underline">{s.empresa_nombre}</Link></Td>
                    <Td>{s.moneda}</Td>
                    <Td derecha><Monto valor={s.ingresos} /></Td>
                    <Td derecha><Monto valor={s.gastos} /></Td>
                    <Td derecha><Monto valor={s.salidas} /></Td>
                    <Td derecha className="font-semibold text-black"><Monto valor={s.saldo} /></Td>
                  </tr>
                ))}
              </tbody>
            </Tabla>
          </Tarjeta>
        </>
      )}

      <Tarjeta className="mb-6 p-4">
        <p className="mb-2 text-sm font-semibold text-black">Empresas</p>
        <div className="flex flex-wrap items-center gap-2">
          {p.empresas.length === 0 && <span className="text-sm text-neutral-500">Ninguna todavía: se vinculan solas al capturar.</span>}
          {p.empresas.map((e) => (
            <span key={e.id} className="inline-flex items-center gap-1 rounded-md bg-white px-2 py-1 text-sm ring-1 ring-neutral-300">
              <Link to={`/empresas/${e.id}`} className="hover:underline">{e.nombre}</Link>
              <button type="button" aria-label={`Desvincular ${e.nombre}`} className="ml-1 text-neutral-400 hover:text-black"
                onClick={() => confirm(`¿Desvincular «${e.nombre}» del proyecto?`) &&
                  accion(() => api.delete(`/proyectos/${p.id}/empresas/${e.id}`), "Empresa desvinculada")}>
                ×
              </button>
            </span>
          ))}
          {sinVincular.length > 0 && (
            <div className="flex items-center gap-2">
              <Select aria-label="Empresa a vincular" value={vincular} onChange={(e) => setVincular(e.target.value)} className="w-56">
                <option value="">Vincular empresa…</option>
                {sinVincular.map((e) => <option key={e.id} value={e.id}>{e.nombre}</option>)}
              </Select>
              <Boton variante="secundario" tamano="sm" disabled={!vincular}
                onClick={() => accion(() => api.post(`/proyectos/${p.id}/empresas`, { empresa_id: vincular }), "Empresa vinculada")
                  .then(() => setVincular(""))}>
                Vincular
              </Boton>
            </div>
          )}
        </div>
      </Tarjeta>

      <PendientesProyecto proyectoId={p.id} />

      <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <h2 className="text-lg font-semibold text-black">Historial</h2>
        <Exportar ruta={`/reportes/historial-proyecto/${p.id}`} query={filtros} nombre={`historial-${p.nombre}`} />
      </div>
      <Tarjeta className="mb-4 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Campo etiqueta="Desde">
            {(fid) => <Input id={fid} type="date" value={filtros.desde} onChange={(e) => cambiar({ desde: e.target.value })} />}
          </Campo>
          <Campo etiqueta="Hasta">
            {(fid) => <Input id={fid} type="date" value={filtros.hasta} onChange={(e) => cambiar({ hasta: e.target.value })} />}
          </Campo>
          <Campo etiqueta="Empresa">
            {(fid) => (
              <Select id={fid} value={filtros.empresa_id} onChange={(e) => cambiar({ empresa_id: e.target.value })}>
                <option value="">Todas</option>
                {p.empresas.map((e) => <option key={e.id} value={e.id}>{e.nombre}</option>)}
              </Select>
            )}
          </Campo>
          <div className="flex items-end">
            <Boton variante="secundario" disabled={!activos} onClick={limpiar} className="w-full">Quitar filtros</Boton>
          </div>
        </div>
      </Tarjeta>
      <ErrorApi error={historial.error} className="mb-4" />
      <Tarjeta>{historial.isLoading || !historial.data ? <Cargando /> : <ReporteTabla reporte={historial.data} />}</Tarjeta>

      <ProyectoForm abierto={editando} proyecto={p} onCerrar={() => setEditando(false)} />
      <EntradaForm abierto={movimiento === "entrada"} proyectoId={p.id} onCerrar={() => setMovimiento(null)} />
      <SalidaForm abierto={movimiento === "salida"} proyectoId={p.id} onCerrar={() => setMovimiento(null)} />
      <CargaMasiva abierto={carga} proyecto={p} onCerrar={() => setCarga(false)} />
    </>
  );
}
