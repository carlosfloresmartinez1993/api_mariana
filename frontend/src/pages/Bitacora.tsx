import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  Boton,
  Campo,
  Cargando,
  EncabezadoPagina,
  ErrorApi,
  Input,
  Modal,
  Paginacion,
  Select,
  Tabla,
  Tarjeta,
  Td,
  Th,
  Vacio,
} from "../components/ui";
import { api } from "../lib/api";
import { fechaHoraLocal } from "../lib/format";
import { useFiltros } from "../lib/filtros";
import { ACCIONES_BITACORA, ENTIDADES_BITACORA, type AccionBitacora, type Pagina, type RegistroBitacora, type Usuario } from "../lib/types";

const LIMITE = 50;
const CLAVES = ["usuario_id", "entidad", "accion", "desde", "hasta"] as const;

/** Resumen de una línea del detalle (p. ej. el correo del usuario creado o la IP del inicio de sesión). */
function resumen(r: RegistroBitacora): string {
  const d = r.detalle as Record<string, unknown>;
  const despues = d.despues as Record<string, unknown> | undefined;
  if (typeof despues?.correo === "string") return despues.correo;
  if (typeof d.correo === "string") return d.correo;
  if (typeof d.motivo === "string") return d.motivo;
  if (typeof d.empresa === "string") return d.proyecto ? `${d.empresa} ↔ ${d.proyecto}` : d.empresa;
  if (typeof d.nombre === "string") return d.nombre;
  if (typeof d.ip === "string") return `IP ${d.ip}`;
  return "";
}

export default function Bitacora() {
  const { filtros, offset, cambiar, limpiar, activos } = useFiltros(CLAVES);
  const [viendo, setViendo] = useState<RegistroBitacora | null>(null);

  const usuarios = useQuery({
    queryKey: ["usuarios", "catalogo"],
    queryFn: () => api.get<Usuario[]>("/usuarios/catalogo"),
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ["bitacora", filtros, offset],
    queryFn: () => api.get<Pagina<RegistroBitacora>>("/bitacora", { ...filtros, limit: LIMITE, offset }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <EncabezadoPagina titulo="Bitácora" descripcion="Todo lo que hace cada usuario, incluido el superusuario. No se puede modificar." />

      <Tarjeta className="mb-4 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Campo etiqueta="Usuario">
            {(id) => (
              <Select id={id} value={filtros.usuario_id} onChange={(e) => cambiar({ usuario_id: e.target.value })}>
                <option value="">Todos</option>
                {usuarios.data?.map((u) => <option key={u.id} value={u.id}>{u.nombre}</option>)}
              </Select>
            )}
          </Campo>
          <Campo etiqueta="Registro">
            {(id) => (
              <Select id={id} value={filtros.entidad} onChange={(e) => cambiar({ entidad: e.target.value })}>
                <option value="">Todos</option>
                {ENTIDADES_BITACORA.map((e) => <option key={e} value={e}>{e}</option>)}
              </Select>
            )}
          </Campo>
          <Campo etiqueta="Acción">
            {(id) => (
              <Select id={id} value={filtros.accion} onChange={(e) => cambiar({ accion: e.target.value })}>
                <option value="">Todas</option>
                {Object.entries(ACCIONES_BITACORA).map(([valor, texto]) => <option key={valor} value={valor}>{texto}</option>)}
              </Select>
            )}
          </Campo>
          <Campo etiqueta="Desde">
            {(id) => <Input id={id} type="date" value={filtros.desde} onChange={(e) => cambiar({ desde: e.target.value })} />}
          </Campo>
          <Campo etiqueta="Hasta">
            {(id) => <Input id={id} type="date" value={filtros.hasta} onChange={(e) => cambiar({ hasta: e.target.value })} />}
          </Campo>
          <div className="flex items-end">
            <Boton variante="secundario" disabled={!activos} onClick={limpiar} className="w-full">Quitar filtros</Boton>
          </div>
        </div>
      </Tarjeta>

      <ErrorApi error={error} className="mb-4" />

      <Tarjeta>
        {isLoading ? (
          <Cargando />
        ) : !data?.items.length ? (
          <Vacio titulo="Sin registros" descripcion={activos ? "No hay registros con esos filtros." : undefined} />
        ) : (
          <>
            <Tabla>
              <thead>
                <tr>
                  <Th>Fecha</Th>
                  <Th>Usuario</Th>
                  <Th>Acción</Th>
                  <Th>Registro</Th>
                  <Th>Detalle</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {data.items.map((r) => (
                  <tr key={r.id} className="cursor-pointer hover:bg-neutral-50" onClick={() => setViendo(r)}>
                    <Td className="whitespace-nowrap">{fechaHoraLocal(r.fecha)}</Td>
                    <Td className="font-medium text-black">{r.usuario_nombre}</Td>
                    <Td>{ACCIONES_BITACORA[r.accion as AccionBitacora] ?? r.accion}</Td>
                    <Td>{r.entidad}</Td>
                    <Td className="max-w-xs truncate text-neutral-500">{resumen(r)}</Td>
                  </tr>
                ))}
              </tbody>
            </Tabla>
            <Paginacion total={data.total} limit={LIMITE} offset={offset} onCambiar={(o) => cambiar({ offset: o })} />
          </>
        )}
      </Tarjeta>

      <Modal abierto={viendo !== null} onCerrar={() => setViendo(null)} ancho="lg"
        titulo={viendo ? `${ACCIONES_BITACORA[viendo.accion] ?? viendo.accion} · ${viendo.entidad}` : ""}
        descripcion={viendo ? `${viendo.usuario_nombre} · ${fechaHoraLocal(viendo.fecha)}` : undefined}>
        <pre className="overflow-x-auto rounded-md bg-neutral-50 p-3 text-xs text-black ring-1 ring-neutral-200">
          {viendo ? JSON.stringify(viendo.detalle, null, 2) : ""}
        </pre>
      </Modal>
    </>
  );
}
