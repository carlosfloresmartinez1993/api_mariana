import { useEffect, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../../lib/api";
import type { Empresa, Proyecto } from "../../lib/types";
import { useEnvio } from "../../lib/useEnvio";
import { useToast } from "../Toast";
import { Boton, Campo, ErrorApi, Input, Modal, PieModal, Textarea } from "../ui";

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

/** Alta o edición de un proyecto: solo se necesita el nombre. */
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

  useEffect(() => {
    if (abierto) {
      setNombre(proyecto?.nombre ?? "");
      setDescripcion(proyecto?.descripcion ?? "");
      limpiar();
    }
  }, [abierto, proyecto, limpiar]);

  function guardar(e: FormEvent) {
    e.preventDefault();
    enviar(async () => {
      const datos = { nombre, descripcion: descripcion.trim() || null };
      if (proyecto) {
        await api.patch(`/proyectos/${proyecto.id}`, datos);
        avisar("Proyecto actualizado");
      } else {
        const nuevo = await api.post<Proyecto>("/proyectos", datos);
        avisar("Proyecto creado");
        onCreado?.(nuevo);
      }
      await qc.invalidateQueries({ queryKey: ["proyectos"] });
      onCerrar();
    });
  }

  return (
    <Modal abierto={abierto} titulo={proyecto ? "Editar proyecto" : "Nuevo proyecto"} onCerrar={onCerrar}
      descripcion={proyecto ? undefined : "Solo se necesita el nombre. Las empresas se vinculan solas al registrar entradas o salidas."}>
      <form onSubmit={guardar} className="space-y-4">
        <Campo etiqueta="Nombre" requerido>
          {(id) => <Input id={id} required autoFocus maxLength={200} value={nombre} onChange={(e) => setNombre(e.target.value)} />}
        </Campo>
        <Campo etiqueta="Descripción">
          {(id) => <Textarea id={id} maxLength={2000} value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />}
        </Campo>
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>{proyecto ? "Guardar" : "Crear proyecto"}</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}
