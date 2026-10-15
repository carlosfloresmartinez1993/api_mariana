import { useEffect, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { Icono } from "../components/Icono";
import { useToast } from "../components/Toast";
import {
  Boton,
  Campo,
  Cargando,
  EncabezadoPagina,
  ErrorApi,
  Input,
  Insignia,
  Modal,
  PieModal,
  Tabla,
  Tarjeta,
  Td,
  Th,
  Vacio,
} from "../components/ui";
import { api } from "../lib/api";
import { useCategorias } from "../lib/queries";
import type { Categoria } from "../lib/types";
import { useEnvio } from "../lib/useEnvio";

function CategoriaForm({ abierto, categoria, onCerrar }: { abierto: boolean; categoria: Categoria | null; onCerrar: () => void }) {
  const avisar = useToast();
  const qc = useQueryClient();
  const { error, enviando, enviar, limpiar } = useEnvio();
  const [nombre, setNombre] = useState("");
  const [descripcion, setDescripcion] = useState("");

  useEffect(() => {
    if (abierto) {
      setNombre(categoria?.nombre ?? "");
      setDescripcion(categoria?.descripcion ?? "");
      limpiar();
    }
  }, [abierto, categoria, limpiar]);

  function guardar(e: FormEvent) {
    e.preventDefault();
    enviar(async () => {
      const datos = { nombre, descripcion: descripcion.trim() || null };
      if (categoria) await api.patch(`/categorias/${categoria.id}`, datos);
      else await api.post("/categorias", datos);
      // El nombre de la categoría aparece en entradas, salidas y reportes.
      await Promise.all(["categorias", "entradas", "salidas", "reportes"].map((k) => qc.invalidateQueries({ queryKey: [k] })));
      avisar(categoria ? "Categoría actualizada" : "Categoría creada");
      onCerrar();
    });
  }

  return (
    <Modal abierto={abierto} titulo={categoria ? "Editar categoría" : "Nueva categoría"} onCerrar={onCerrar}>
      <form onSubmit={guardar} className="space-y-4">
        <Campo etiqueta="Nombre" requerido>
          {(id) => <Input id={id} required autoFocus maxLength={100} value={nombre} onChange={(e) => setNombre(e.target.value)}
            placeholder="Materiales, nómina, renta…" />}
        </Campo>
        <Campo etiqueta="Descripción">
          {(id) => <Input id={id} maxLength={255} value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />}
        </Campo>
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>{categoria ? "Guardar" : "Crear categoría"}</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}

export default function Categorias() {
  const { puedeCorregir } = useAuth();
  const avisar = useToast();
  const qc = useQueryClient();
  const { data, isLoading, error } = useCategorias();
  const [form, setForm] = useState<{ categoria: Categoria | null } | null>(null);

  async function alternar(c: Categoria) {
    try {
      await api.post(`/categorias/${c.id}/${c.activa ? "desactivar" : "activar"}`);
      await qc.invalidateQueries({ queryKey: ["categorias"] });
      avisar(c.activa ? "Categoría desactivada" : "Categoría activada");
    } catch (e) {
      avisar((e as Error).message, "error");
    }
  }

  return (
    <>
      <EncabezadoPagina
        titulo="Categorías"
        descripcion="Clasifican entradas y salidas (opcional). Una categoría desactivada ya no se ofrece al capturar, pero los movimientos la conservan."
        acciones={<Boton onClick={() => setForm({ categoria: null })}><Icono nombre="mas" className="size-4" /> Nueva categoría</Boton>}
      />
      <ErrorApi error={error} className="mb-4" />
      <Tarjeta>
        {isLoading ? (
          <Cargando />
        ) : !data?.length ? (
          <Vacio titulo="Sin categorías" descripcion="Crea las que uses para clasificar entradas y salidas."
            accion={<Boton onClick={() => setForm({ categoria: null })}>Nueva categoría</Boton>} />
        ) : (
          <Tabla>
            <thead>
              <tr>
                <Th>Categoría</Th>
                <Th>Descripción</Th>
                <Th>Registrada por</Th>
                <Th><span className="sr-only">Acciones</span></Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {data.map((c) => (
                <tr key={c.id} className={c.activa ? "hover:bg-neutral-50" : "text-neutral-400"}>
                  <Td className="font-medium text-black">
                    {c.nombre} {!c.activa && <Insignia tono="tenue">Desactivada</Insignia>}
                  </Td>
                  <Td>{c.descripcion}</Td>
                  <Td className="text-neutral-500">{c.creado_por_nombre}</Td>
                  <Td className="whitespace-nowrap text-right">
                    {puedeCorregir(c) && (
                      <>
                        <Boton variante="fantasma" tamano="sm" onClick={() => setForm({ categoria: c })}>Editar</Boton>
                        <Boton variante="fantasma" tamano="sm" onClick={() => alternar(c)}>{c.activa ? "Desactivar" : "Activar"}</Boton>
                      </>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Tabla>
        )}
      </Tarjeta>
      <CategoriaForm abierto={form !== null} categoria={form?.categoria ?? null} onCerrar={() => setForm(null)} />
    </>
  );
}
