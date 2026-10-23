import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { api } from "../lib/api";
import { montoParaApi, montoParaEditar } from "../lib/format";
import { useCategorias } from "../lib/queries";
import { MONEDAS, NOMBRE_TIPO_ESTIMADO, type Moneda, type PartidaEstimada, type Proyecto, type Reporte, type TipoEstimado } from "../lib/types";
import { useEnvio } from "../lib/useEnvio";
import { Icono } from "./Icono";
import { ReporteTabla } from "./ReporteTabla";
import { useToast } from "./Toast";
import { Boton, Campo, Cargando, ErrorApi, Input, InputMonto, Modal, Monto, Opciones, PieModal, Select, Tabla, Tarjeta, Td, Th, Vacio } from "./ui";

const TIPOS = [{ valor: "ingreso" as const, texto: "Ingreso" }, { valor: "gasto" as const, texto: "Gasto" }];

/** Partida capturada en el formulario (montos con comas, tal como se escriben). */
export interface PartidaBorrador {
  tipo: TipoEstimado;
  categoria_id: string;
  concepto: string;
  moneda: Moneda;
  monto: string;
}

export const partidaVacia = (): PartidaBorrador => ({ tipo: "gasto", categoria_id: "", concepto: "", moneda: "MXN", monto: "" });

export function partidaParaApi(p: PartidaBorrador) {
  return { tipo: p.tipo, categoria_id: p.categoria_id || null, concepto: p.concepto.trim() || null, moneda: p.moneda,
    monto: montoParaApi(p.monto) };
}

/** Suma de las partidas por tipo y moneda, con las mismas claves que los totales estimados del proyecto. */
export function totalesDePartidas(partidas: { tipo: TipoEstimado; moneda: Moneda; monto: string }[]) {
  const totales: Record<string, number> = {};
  for (const p of partidas) {
    const clave = `estimado_${p.tipo === "ingreso" ? "ingresos" : "gastos"}_${p.moneda.toLowerCase()}`;
    totales[clave] = (totales[clave] ?? 0) + Number(montoParaApi(p.monto) || 0);
  }
  return totales;
}

function useCategoriasActivas() {
  return (useCategorias().data ?? []).filter((c) => c.activa);
}

/** Lista editable de partidas para el alta del proyecto. */
export function EditorPartidas({ partidas, onCambiar }: { partidas: PartidaBorrador[]; onCambiar: (p: PartidaBorrador[]) => void }) {
  const categorias = useCategoriasActivas();
  const cambiar = (i: number, cambio: Partial<PartidaBorrador>) =>
    onCambiar(partidas.map((p, j) => (i === j ? { ...p, ...cambio } : p)));

  return (
    <div className="space-y-2">
      {partidas.map((p, i) => (
        <div key={i} className="grid items-end gap-2 rounded-md p-2 ring-1 ring-neutral-200 sm:grid-cols-[auto_1fr_1fr_auto_8rem_auto]">
          <Campo etiqueta="Tipo">{() => <Opciones valor={p.tipo} opciones={TIPOS} onCambiar={(tipo) => cambiar(i, { tipo })} />}</Campo>
          <Campo etiqueta="Categoría">
            {(id) => (
              <Select id={id} value={p.categoria_id} onChange={(e) => cambiar(i, { categoria_id: e.target.value })}>
                <option value="">Sin categoría</option>
                {categorias.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
              </Select>
            )}
          </Campo>
          <Campo etiqueta="Concepto">
            {(id) => <Input id={id} maxLength={255} value={p.concepto} placeholder="Opcional" onChange={(e) => cambiar(i, { concepto: e.target.value })} />}
          </Campo>
          <Campo etiqueta="Moneda">
            {() => <Opciones valor={p.moneda} opciones={MONEDAS.map((m) => ({ valor: m, texto: m }))} onCambiar={(moneda) => cambiar(i, { moneda })} />}
          </Campo>
          <Campo etiqueta="Monto" requerido>
            {(id) => <InputMonto id={id} required value={p.monto} placeholder="0.00" onChange={(monto) => cambiar(i, { monto })} />}
          </Campo>
          <Boton variante="fantasma" tamano="sm" aria-label="Quitar partida" onClick={() => onCambiar(partidas.filter((_, j) => j !== i))}>Quitar</Boton>
        </div>
      ))}
      <Boton variante="secundario" tamano="sm" onClick={() => onCambiar([...partidas, partidaVacia()])}>
        <Icono nombre="mas" className="size-4" /> Agregar ingreso o gasto por categoría
      </Boton>
    </div>
  );
}

function PartidaForm({ abierto, proyectoId, partida, onCerrar }: {
  abierto: boolean;
  proyectoId: string;
  partida: PartidaEstimada | null;
  onCerrar: () => void;
}) {
  const avisar = useToast();
  const qc = useQueryClient();
  const { error, enviando, enviar, limpiar } = useEnvio();
  const [datos, setDatos] = useState<PartidaBorrador>(partidaVacia());

  useEffect(() => {
    if (abierto) {
      setDatos(partida ? { tipo: partida.tipo, categoria_id: partida.categoria_id ?? "", concepto: partida.concepto ?? "",
        moneda: partida.moneda, monto: montoParaEditar(partida.monto) } : partidaVacia());
      limpiar();
    }
  }, [abierto, partida, limpiar]);

  function guardar(e: FormEvent) {
    e.preventDefault();
    enviar(async () => {
      if (partida) await api.patch(`/partidas-estimadas/${partida.id}`, partidaParaApi(datos));
      else await api.post(`/proyectos/${proyectoId}/partidas-estimadas`, partidaParaApi(datos));
      await Promise.all(["partidas-estimadas", "proyectos", "reportes"].map((k) => qc.invalidateQueries({ queryKey: [k] })));
      avisar(partida ? "Partida actualizada" : "Partida agregada");
      onCerrar();
    });
  }

  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={partida ? "Editar partida estimada" : "Nuevo ingreso o gasto estimado"}
      descripcion="No afecta saldos. Los totales estimados del proyecto se calculan con estas partidas.">
      <form onSubmit={guardar}>
        <EditorUna datos={datos} onCambiar={setDatos} />
        <ErrorApi error={error} className="mt-4" />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>{partida ? "Guardar" : "Agregar"}</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}

function EditorUna({ datos, onCambiar }: { datos: PartidaBorrador; onCambiar: (p: PartidaBorrador) => void }) {
  const categorias = useCategoriasActivas();
  const cambiar = (c: Partial<PartidaBorrador>) => onCambiar({ ...datos, ...c });
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Campo etiqueta="Tipo">{() => <Opciones valor={datos.tipo} opciones={TIPOS} onCambiar={(tipo) => cambiar({ tipo })} />}</Campo>
        <Campo etiqueta="Moneda">
          {() => <Opciones valor={datos.moneda} opciones={MONEDAS.map((m) => ({ valor: m, texto: m }))} onCambiar={(moneda) => cambiar({ moneda })} />}
        </Campo>
      </div>
      <Campo etiqueta="Categoría" ayuda="Se compara contra las entradas y salidas reales de esa categoría.">
        {(id) => (
          <Select id={id} value={datos.categoria_id} onChange={(e) => cambiar({ categoria_id: e.target.value })}>
            <option value="">Sin categoría</option>
            {categorias.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </Select>
        )}
      </Campo>
      <div className="grid gap-4 sm:grid-cols-2">
        <Campo etiqueta="Concepto">
          {(id) => <Input id={id} maxLength={255} value={datos.concepto} placeholder="Opcional" onChange={(e) => cambiar({ concepto: e.target.value })} />}
        </Campo>
        <Campo etiqueta={`Monto (${datos.moneda})`} requerido>
          {(id) => <InputMonto id={id} required value={datos.monto} placeholder="0.00" onChange={(monto) => cambiar({ monto })} />}
        </Campo>
      </div>
    </div>
  );
}

/** Detalle del proyecto: partidas estimadas y comparación por categoría contra lo real. */
export function PartidasProyecto({ proyecto }: { proyecto: Proyecto }) {
  const { puedeCorregir } = useAuth();
  const avisar = useToast();
  const qc = useQueryClient();
  const [form, setForm] = useState<{ partida: PartidaEstimada | null } | null>(null);
  const partidas = useQuery({
    queryKey: ["partidas-estimadas", proyecto.id],
    queryFn: () => api.get<PartidaEstimada[]>(`/proyectos/${proyecto.id}/partidas-estimadas`),
  });
  const comparacion = useQuery({
    queryKey: ["reportes", "estimado-por-categoria", proyecto.id],
    queryFn: () => api.get<Reporte>("/reportes/estimado-vs-real", { por_categoria: true, proyecto_id: proyecto.id }),
    enabled: !!partidas.data?.length,
  });

  async function eliminar(p: PartidaEstimada) {
    if (!confirm(`¿Eliminar la partida «${p.concepto ?? p.categoria_nombre ?? NOMBRE_TIPO_ESTIMADO[p.tipo]}»?`)) return;
    try {
      await api.delete(`/partidas-estimadas/${p.id}`);
      await Promise.all(["partidas-estimadas", "proyectos", "reportes"].map((k) => qc.invalidateQueries({ queryKey: [k] })));
      avisar("Partida eliminada");
    } catch (e) {
      avisar((e as Error).message, "error");
    }
  }

  return (
    <>
      <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-black">Proyección por categoría</h2>
          <p className="text-sm text-neutral-500">
            Ingresos y gastos estimados por categoría y concepto. Si hay partidas, los totales estimados son su suma. No afectan saldos.
          </p>
        </div>
        {proyecto.activo && (
          <Boton tamano="sm" onClick={() => setForm({ partida: null })}><Icono nombre="mas" className="size-4" /> Agregar</Boton>
        )}
      </div>
      <ErrorApi error={partidas.error} className="mb-3" />
      <Tarjeta className="mb-4">
        {partidas.isLoading ? (
          <Cargando />
        ) : !partidas.data?.length ? (
          <Vacio titulo="Sin partidas estimadas" descripcion="Agrega ingresos o gastos estimados por categoría para compararlos contra lo real." />
        ) : (
          <Tabla>
            <thead>
              <tr><Th>Tipo</Th><Th>Categoría</Th><Th>Concepto</Th><Th derecha>Monto</Th><Th><span className="sr-only">Acciones</span></Th></tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {partidas.data.map((p) => (
                <tr key={p.id} className="hover:bg-neutral-50">
                  <Td>{NOMBRE_TIPO_ESTIMADO[p.tipo]}</Td>
                  <Td>{p.categoria_nombre ?? <span className="text-neutral-400">Sin categoría</span>}</Td>
                  <Td>{p.concepto ?? "—"}</Td>
                  <Td derecha><Monto valor={p.monto} moneda={p.moneda} /></Td>
                  <Td className="whitespace-nowrap text-right">
                    {puedeCorregir(p) && (
                      <>
                        <Boton variante="fantasma" tamano="sm" onClick={() => setForm({ partida: p })}>Editar</Boton>
                        <Boton variante="fantasma" tamano="sm" onClick={() => eliminar(p)}>Eliminar</Boton>
                      </>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Tabla>
        )}
      </Tarjeta>
      {!!partidas.data?.length && (
        <>
          <h3 className="mb-2 text-sm font-semibold text-black">Estimado contra real por categoría</h3>
          <ErrorApi error={comparacion.error} className="mb-3" />
          <Tarjeta className="mb-6">
            {comparacion.isLoading || !comparacion.data ? <Cargando /> : <ReporteTabla reporte={comparacion.data} />}
          </Tarjeta>
        </>
      )}
      <PartidaForm abierto={form !== null} proyectoId={proyecto.id} partida={form?.partida ?? null} onCerrar={() => setForm(null)} />
    </>
  );
}
