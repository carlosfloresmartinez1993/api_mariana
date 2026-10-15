import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { api } from "../lib/api";
import { fecha, hoyISO, montoParaApi, montoParaEditar } from "../lib/format";
import { MONEDAS, NOMBRE_TIPO_PENDIENTE, type Moneda, type Pendiente, type TipoPendiente } from "../lib/types";
import { useEnvio } from "../lib/useEnvio";
import { Icono } from "./Icono";
import { useToast } from "./Toast";
import {
  Boton,
  Campo,
  Cargando,
  ErrorApi,
  Input,
  InputMonto,
  Insignia,
  Modal,
  Monto,
  Opciones,
  PieModal,
  Tabla,
  Tarjeta,
  Td,
  Textarea,
  Th,
  Vacio,
} from "./ui";

export function usePendientes(proyectoId: string, todas: boolean) {
  return useQuery({
    queryKey: ["pendientes", proyectoId, todas],
    queryFn: () => api.get<Pendiente[]>("/pendientes", { proyecto_id: proyectoId, estado: todas ? "todas" : "pendientes" }),
  });
}

function PendienteForm({ abierto, proyectoId, pendiente, onCerrar }: {
  abierto: boolean;
  proyectoId: string;
  pendiente: Pendiente | null;
  onCerrar: () => void;
}) {
  const avisar = useToast();
  const qc = useQueryClient();
  const { error, enviando, enviar, limpiar } = useEnvio();
  const [tipo, setTipo] = useState<TipoPendiente>("por_cobrar");
  const [concepto, setConcepto] = useState("");
  const [contraparte, setContraparte] = useState("");
  const [moneda, setMoneda] = useState<Moneda>("MXN");
  const [monto, setMonto] = useState("");
  const [vencimiento, setVencimiento] = useState("");
  const [nota, setNota] = useState("");

  useEffect(() => {
    if (abierto) {
      setTipo(pendiente?.tipo ?? "por_cobrar");
      setConcepto(pendiente?.concepto ?? "");
      setContraparte(pendiente?.contraparte ?? "");
      setMoneda(pendiente?.moneda ?? "MXN");
      setMonto(montoParaEditar(pendiente?.monto));
      setVencimiento(pendiente?.fecha_vencimiento ?? "");
      setNota(pendiente?.nota ?? "");
      limpiar();
    }
  }, [abierto, pendiente, limpiar]);

  function guardar(e: FormEvent) {
    e.preventDefault();
    enviar(async () => {
      const datos = {
        tipo, concepto, contraparte: contraparte.trim() || null, moneda, monto: montoParaApi(monto),
        fecha_vencimiento: vencimiento || null, nota: nota.trim() || null,
      };
      if (pendiente) await api.patch(`/pendientes/${pendiente.id}`, datos);
      else await api.post(`/proyectos/${proyectoId}/pendientes`, datos);
      await Promise.all(["pendientes", "reportes"].map((k) => qc.invalidateQueries({ queryKey: [k] })));
      avisar(pendiente ? "Partida actualizada" : "Partida agregada");
      onCerrar();
    });
  }

  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={pendiente ? "Editar partida" : "Nueva cuenta por cobrar o por pagar"}
      descripcion="No afecta saldos. Cuando cobres o pagues, registra la entrada o salida y marca la partida como liquidada.">
      <form onSubmit={guardar} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Tipo">
            {() => <Opciones valor={tipo} onCambiar={setTipo}
              opciones={[{ valor: "por_cobrar", texto: "Por cobrar" }, { valor: "por_pagar", texto: "Por pagar" }]} />}
          </Campo>
          <Campo etiqueta="Moneda">
            {() => <Opciones valor={moneda} onCambiar={setMoneda} opciones={MONEDAS.map((m) => ({ valor: m, texto: m }))} />}
          </Campo>
        </div>
        <Campo etiqueta="Concepto" requerido>
          {(id) => <Input id={id} required maxLength={255} value={concepto} onChange={(e) => setConcepto(e.target.value)}
            placeholder={tipo === "por_cobrar" ? "Estimación 3, anticipo pendiente…" : "Factura de acero, nómina pendiente…"} />}
        </Campo>
        <div className="grid gap-4 sm:grid-cols-3">
          <Campo etiqueta={tipo === "por_cobrar" ? "Cliente" : "Proveedor"} className="sm:col-span-1">
            {(id) => <Input id={id} maxLength={200} value={contraparte} onChange={(e) => setContraparte(e.target.value)} />}
          </Campo>
          <Campo etiqueta={`Monto (${moneda})`} requerido>
            {(id) => <InputMonto id={id} required value={monto} onChange={setMonto} placeholder="0.00" />}
          </Campo>
          <Campo etiqueta="Vencimiento">
            {(id) => <Input id={id} type="date" value={vencimiento} onChange={(e) => setVencimiento(e.target.value)} />}
          </Campo>
        </div>
        <Campo etiqueta="Nota">
          {(id) => <Textarea id={id} maxLength={2000} value={nota} onChange={(e) => setNota(e.target.value)} />}
        </Campo>
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>{pendiente ? "Guardar" : "Agregar"}</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}

/** Cuentas por cobrar y por pagar de un proyecto, con totales pendientes por moneda. */
export function PendientesProyecto({ proyectoId }: { proyectoId: string }) {
  const { puedeCorregir } = useAuth();
  const avisar = useToast();
  const qc = useQueryClient();
  const [todas, setTodas] = useState(false);
  const [form, setForm] = useState<{ pendiente: Pendiente | null } | null>(null);
  const { data, isLoading, error } = usePendientes(proyectoId, todas);

  async function accion(fn: () => Promise<unknown>, mensaje: string) {
    try {
      await fn();
      await Promise.all(["pendientes", "reportes"].map((k) => qc.invalidateQueries({ queryKey: [k] })));
      avisar(mensaje);
    } catch (e) {
      avisar((e as Error).message, "error");
    }
  }

  const pendientes = (data ?? []).filter((p) => !p.liquidada);
  const totales = MONEDAS.map((m) => ({
    moneda: m,
    cobrar: pendientes.filter((p) => p.moneda === m && p.tipo === "por_cobrar").reduce((s, p) => s + Number(p.monto), 0),
    pagar: pendientes.filter((p) => p.moneda === m && p.tipo === "por_pagar").reduce((s, p) => s + Number(p.monto), 0),
  })).filter((t) => t.cobrar || t.pagar);

  return (
    <>
      <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-black">Cuentas por cobrar y por pagar</h2>
          <p className="text-sm text-neutral-500">No afectan saldos; sirven para saber lo que falta cobrar o pagar.</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-neutral-600">
            <input type="checkbox" checked={todas} onChange={(e) => setTodas(e.target.checked)} className="size-4 accent-black" />
            Ver liquidadas
          </label>
          <Boton tamano="sm" onClick={() => setForm({ pendiente: null })}><Icono nombre="mas" className="size-4" /> Agregar</Boton>
        </div>
      </div>
      {totales.length > 0 && (
        <div className="mb-3 grid gap-3 sm:grid-cols-2">
          {totales.map((t) => (
            <Tarjeta key={t.moneda} className="grid grid-cols-3 gap-2 p-3 text-sm">
              <div><p className="text-neutral-500">Por cobrar {t.moneda}</p><Monto valor={t.cobrar} /></div>
              <div><p className="text-neutral-500">Por pagar {t.moneda}</p><Monto valor={t.pagar} /></div>
              <div><p className="text-neutral-500">Diferencia</p><Monto valor={t.cobrar - t.pagar} className="font-semibold" /></div>
            </Tarjeta>
          ))}
        </div>
      )}
      <ErrorApi error={error} className="mb-3" />
      <Tarjeta className="mb-6">
        {isLoading ? (
          <Cargando />
        ) : !data?.length ? (
          <Vacio titulo={todas ? "Sin partidas" : "Nada pendiente"} descripcion="Agrega lo que le deben al proyecto o lo que el proyecto debe." />
        ) : (
          <Tabla>
            <thead>
              <tr>
                <Th>Tipo</Th><Th>Concepto</Th><Th derecha>Monto</Th><Th>Vencimiento</Th><Th>Estado</Th>
                <Th><span className="sr-only">Acciones</span></Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {data.map((p) => (
                <tr key={p.id} className={p.liquidada ? "text-neutral-400" : "hover:bg-neutral-50"}>
                  <Td>{NOMBRE_TIPO_PENDIENTE[p.tipo]}</Td>
                  <Td>
                    <p className="text-black">{p.concepto}</p>
                    {(p.contraparte || p.nota) && <p className="text-xs text-neutral-500">{[p.contraparte, p.nota].filter(Boolean).join(" · ")}</p>}
                  </Td>
                  <Td derecha><Monto valor={p.monto} moneda={p.moneda} /></Td>
                  <Td className="whitespace-nowrap">{fecha(p.fecha_vencimiento)}</Td>
                  <Td>
                    {p.liquidada ? <Insignia tono="tenue">Liquidada {fecha(p.fecha_liquidacion)}</Insignia>
                      : p.vencida ? <span className="text-xs font-semibold text-red-600">VENCIDA</span> : <Insignia>Pendiente</Insignia>}
                  </Td>
                  <Td className="whitespace-nowrap text-right">
                    {puedeCorregir(p) && (
                      <>
                        {!p.liquidada ? (
                          <Boton variante="fantasma" tamano="sm" onClick={() => accion(
                            () => api.patch(`/pendientes/${p.id}`, { liquidada: true, fecha_liquidacion: hoyISO() }), "Partida liquidada")}>
                            Liquidar
                          </Boton>
                        ) : (
                          <Boton variante="fantasma" tamano="sm" onClick={() => accion(
                            () => api.patch(`/pendientes/${p.id}`, { liquidada: false }), "Partida reabierta")}>
                            Reabrir
                          </Boton>
                        )}
                        <Boton variante="fantasma" tamano="sm" onClick={() => setForm({ pendiente: p })}>Editar</Boton>
                        <Boton variante="fantasma" tamano="sm" onClick={() => confirm(`¿Eliminar «${p.concepto}»?`) &&
                          accion(() => api.delete(`/pendientes/${p.id}`), "Partida eliminada")}>Eliminar</Boton>
                      </>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Tabla>
        )}
      </Tarjeta>
      <PendienteForm abierto={form !== null} proyectoId={proyectoId} pendiente={form?.pendiente ?? null} onCerrar={() => setForm(null)} />
    </>
  );
}

/** Proyección contra lo real del proyecto. Se muestra solo si hay algún estimado. */
export function ProyeccionVsReal({ proyecto }: {
  proyecto: {
    estimado_ingresos_mxn: string | null; estimado_gastos_mxn: string | null;
    estimado_ingresos_usd: string | null; estimado_gastos_usd: string | null;
    trabajadores_estimados: number | null; fecha_inicio_estimada: string | null; fecha_fin_estimada: string | null;
    saldos: { moneda: string; ingresos: string; salidas: string }[];
  };
}) {
  const filas = MONEDAS.map((m) => {
    const sufijo = m.toLowerCase() as "mxn" | "usd";
    const real = proyecto.saldos.find((s) => s.moneda === m);
    return {
      moneda: m,
      estIngresos: proyecto[`estimado_ingresos_${sufijo}`],
      estGastos: proyecto[`estimado_gastos_${sufijo}`],
      ingresos: Number(real?.ingresos ?? 0),
      salidas: Number(real?.salidas ?? 0),
    };
  }).filter((f) => f.estIngresos !== null || f.estGastos !== null);
  const hayFechas = proyecto.fecha_inicio_estimada || proyecto.fecha_fin_estimada || proyecto.trabajadores_estimados !== null;
  if (!filas.length && !hayFechas) return null;
  const avance = (real: number, est: string | null) => (est && Number(est) ? `${((real * 100) / Number(est)).toFixed(0)} %` : "");

  return (
    <>
      <h2 className="mb-1 text-lg font-semibold text-black">Proyección contra lo real</h2>
      <p className="mb-3 text-sm text-neutral-500">Los estimados no afectan saldos.</p>
      <Tarjeta className="mb-6">
        {hayFechas && (
          <div className="grid gap-3 border-b border-neutral-200 p-4 text-sm sm:grid-cols-3">
            <div><p className="text-neutral-500">Inicio estimado</p><p>{fecha(proyecto.fecha_inicio_estimada)}</p></div>
            <div><p className="text-neutral-500">Terminación estimada</p><p>{fecha(proyecto.fecha_fin_estimada)}</p></div>
            <div><p className="text-neutral-500">Trabajadores estimados</p><p>{proyecto.trabajadores_estimados ?? "—"}</p></div>
          </div>
        )}
        {filas.length > 0 && (
          <Tabla>
            <thead>
              <tr>
                <Th>Moneda</Th><Th derecha>Ingresos estimados</Th><Th derecha>Ingresos reales</Th><Th derecha>Avance</Th>
                <Th derecha>Gastos estimados</Th><Th derecha>Salidas reales</Th><Th derecha>Avance</Th>
                <Th derecha>Resultado estimado</Th><Th derecha>Resultado real</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {filas.map((f) => (
                <tr key={f.moneda}>
                  <Td>{f.moneda}</Td>
                  <Td derecha>{f.estIngresos === null ? "—" : <Monto valor={f.estIngresos} />}</Td>
                  <Td derecha><Monto valor={f.ingresos} /></Td>
                  <Td derecha>{avance(f.ingresos, f.estIngresos)}</Td>
                  <Td derecha>{f.estGastos === null ? "—" : <Monto valor={f.estGastos} />}</Td>
                  <Td derecha><Monto valor={f.salidas} /></Td>
                  <Td derecha>{avance(f.salidas, f.estGastos)}</Td>
                  <Td derecha><Monto valor={Number(f.estIngresos ?? 0) - Number(f.estGastos ?? 0)} /></Td>
                  <Td derecha className="font-semibold"><Monto valor={f.ingresos - f.salidas} /></Td>
                </tr>
              ))}
            </tbody>
          </Tabla>
        )}
      </Tarjeta>
    </>
  );
}

