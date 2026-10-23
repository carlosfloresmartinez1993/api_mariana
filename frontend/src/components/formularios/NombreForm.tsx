import { useEffect, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { montoParaApi, montoParaEditar } from "../../lib/format";
import type { Empresa, Proyecto } from "../../lib/types";
import { useEnvio } from "../../lib/useEnvio";
import { EditorPartidas, partidaParaApi, totalesDePartidas, type PartidaBorrador } from "../PartidasEstimadas";
import { useToast } from "../Toast";
import { Boton, Campo, ErrorApi, Input, InputMonto, Modal, PieModal, Textarea } from "../ui";

/** Alta o edición de una empresa: solo se necesita el nombre. */
export function EmpresaForm({ abierto, empresa, onCerrar, onCreada }: {
  abierto: boolean;
  empresa?: Empresa | null;
  onCerrar: () => void;
  onCreada?: (empresa: Empresa) => void;
}) {
  const avisar = useToast();
  const qc = useQueryClient();
  const { error, enviando, enviar, limpiar } = useEnvio();
  const [nombre, setNombre] = useState("");

  useEffect(() => {
    if (abierto) {
      setNombre(empresa?.nombre ?? "");
      limpiar();
    }
  }, [abierto, empresa, limpiar]);

  function guardar(e: FormEvent) {
    e.preventDefault();
    enviar(async () => {
      if (empresa) {
        await api.patch(`/empresas/${empresa.id}`, { nombre });
        avisar("Empresa actualizada");
      } else {
        const nueva = await api.post<Empresa>("/empresas", { nombre });
        avisar("Empresa creada");
        onCreada?.(nueva);
      }
      await qc.invalidateQueries({ queryKey: ["empresas"] });
      await qc.invalidateQueries({ queryKey: ["proyectos"] });
      onCerrar();
    });
  }

  return (
    <Modal abierto={abierto} titulo={empresa ? "Editar empresa" : "Nueva empresa"} onCerrar={onCerrar}
      descripcion={empresa ? undefined : "Solo se necesita el nombre. Las cuentas de banco y las cajas se agregan después."}>
      <form onSubmit={guardar} className="space-y-4">
        <Campo etiqueta="Nombre" requerido>
          {(id) => <Input id={id} required autoFocus maxLength={200} value={nombre} onChange={(e) => setNombre(e.target.value)} />}
        </Campo>
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>{empresa ? "Guardar" : "Crear empresa"}</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}

const MONTOS_ESTIMADOS = [
  ["estimado_ingresos_mxn", "Ingresos estimados (MXN)"],
  ["estimado_gastos_mxn", "Gastos estimados (MXN)"],
  ["estimado_ingresos_usd", "Ingresos estimados (USD)"],
  ["estimado_gastos_usd", "Gastos estimados (USD)"],
] as const;

type ClaveMonto = (typeof MONTOS_ESTIMADOS)[number][0];

/** Alta o edición de un proyecto: solo se necesita el nombre. Las proyecciones son opcionales y no afectan saldos. */
export function ProyectoForm({ abierto, proyecto, onCerrar, onCreado }: {
  abierto: boolean;
  proyecto?: Proyecto | null;
  onCerrar: () => void;
  onCreado?: (proyecto: Proyecto) => void;
}) {
  const avisar = useToast();
  const qc = useQueryClient();
  const { error, enviando, enviar, limpiar } = useEnvio();
  const [nombre, setNombre] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [montos, setMontos] = useState<Record<ClaveMonto, string>>(
    { estimado_ingresos_mxn: "", estimado_gastos_mxn: "", estimado_ingresos_usd: "", estimado_gastos_usd: "" });
  const [trabajadores, setTrabajadores] = useState("");
  const [inicio, setInicio] = useState("");
  const [fin, setFin] = useState("");
  const [partidas, setPartidas] = useState<PartidaBorrador[]>([]);
  // Con partidas, los totales estimados son su suma y no se capturan a mano.
  const conPartidas = proyecto ? proyecto.num_partidas_estimadas > 0 : partidas.length > 0;
  const sumas = totalesDePartidas(partidas);
  const valorMonto = (clave: ClaveMonto) =>
    !conPartidas ? montos[clave] : proyecto ? montoParaEditar(proyecto[clave]) : sumas[clave] ? montoParaEditar(sumas[clave].toFixed(2)) : "";

  useEffect(() => {
    if (abierto) {
      setPartidas([]);
      setNombre(proyecto?.nombre ?? "");
      setDescripcion(proyecto?.descripcion ?? "");
      setMontos({
        estimado_ingresos_mxn: montoParaEditar(proyecto?.estimado_ingresos_mxn),
        estimado_gastos_mxn: montoParaEditar(proyecto?.estimado_gastos_mxn),
        estimado_ingresos_usd: montoParaEditar(proyecto?.estimado_ingresos_usd),
        estimado_gastos_usd: montoParaEditar(proyecto?.estimado_gastos_usd),
      });
      setTrabajadores(proyecto?.trabajadores_estimados?.toString() ?? "");
      setInicio(proyecto?.fecha_inicio_estimada ?? "");
      setFin(proyecto?.fecha_fin_estimada ?? "");
      limpiar();
    }
  }, [abierto, proyecto, limpiar]);

  function guardar(e: FormEvent) {
    e.preventDefault();
    enviar(async () => {
      const datos = {
        nombre,
        descripcion: descripcion.trim() || null,
        ...(conPartidas ? {} : Object.fromEntries(MONTOS_ESTIMADOS.map(([clave]) => [clave, montos[clave] ? montoParaApi(montos[clave]) : null]))),
        ...(proyecto ? {} : { partidas: partidas.map(partidaParaApi) }),
        trabajadores_estimados: trabajadores ? Number(trabajadores) : null,
        fecha_inicio_estimada: inicio || null,
        fecha_fin_estimada: fin || null,
      };
      if (proyecto) {
        await api.patch(`/proyectos/${proyecto.id}`, datos);
        avisar("Proyecto actualizado");
      } else {
        const nuevo = await api.post<Proyecto>("/proyectos", datos);
        avisar("Proyecto creado");
        onCreado?.(nuevo);
      }
      await qc.invalidateQueries({ queryKey: ["proyectos"] });
      await qc.invalidateQueries({ queryKey: ["reportes"] });
      onCerrar();
    });
  }

  return (
    <Modal abierto={abierto} titulo={proyecto ? "Editar proyecto" : "Nuevo proyecto"} onCerrar={onCerrar} ancho={proyecto ? "lg" : "xl"}
      descripcion={proyecto ? undefined : "Solo se necesita el nombre. Las empresas se vinculan solas al registrar entradas o salidas."}>
      <form onSubmit={guardar} className="space-y-4">
        <Campo etiqueta="Nombre" requerido>
          {(id) => <Input id={id} required autoFocus maxLength={200} value={nombre} onChange={(e) => setNombre(e.target.value)} />}
        </Campo>
        <Campo etiqueta="Descripción">
          {(id) => <Textarea id={id} maxLength={2000} value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />}
        </Campo>
        <fieldset className="space-y-4 rounded-md p-3 ring-1 ring-neutral-200">
          <legend className="px-1 text-sm font-semibold text-black">Proyección (opcional)</legend>
          <p className="text-xs text-neutral-500">
            Solo para comparar al final lo estimado contra lo real. No afecta ningún saldo.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            {MONTOS_ESTIMADOS.map(([clave, etiqueta]) => (
              <Campo key={clave} etiqueta={etiqueta}>
                {(id) => <InputMonto id={id} value={valorMonto(clave)} placeholder="0.00" disabled={conPartidas}
                  onChange={(v) => setMontos((m) => ({ ...m, [clave]: v }))} />}
              </Campo>
            ))}
          </div>
          {proyecto ? (
            conPartidas && <p className="text-xs text-neutral-500">Los totales se calculan con las partidas por categoría; edítalas en el detalle del proyecto.</p>
          ) : (
            <div>
              <p className="mb-2 text-sm font-medium text-neutral-800">Por categoría o concepto (opcional)</p>
              <p className="mb-2 text-xs text-neutral-500">Si agregas partidas, los totales de arriba se calculan solos con su suma.</p>
              <EditorPartidas partidas={partidas} onCambiar={setPartidas} />
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-3">
            <Campo etiqueta="Trabajadores estimados">
              {(id) => <Input id={id} type="number" min={0} step={1} value={trabajadores} onChange={(e) => setTrabajadores(e.target.value)} />}
            </Campo>
            <Campo etiqueta="Inicio estimado">
              {(id) => <Input id={id} type="date" value={inicio} onChange={(e) => setInicio(e.target.value)} />}
            </Campo>
            <Campo etiqueta="Terminación estimada">
              {(id) => <Input id={id} type="date" min={inicio || undefined} value={fin} onChange={(e) => setFin(e.target.value)} />}
            </Campo>
          </div>
        </fieldset>
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>{proyecto ? "Guardar" : "Crear proyecto"}</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}
