import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ProyectoForm } from "../components/formularios/NombreForm";
import { Icono } from "../components/Icono";
import {
  Boton,
  Campo,
  Cargando,
  EncabezadoPagina,
  ErrorApi,
  Input,
  Insignia,
  Paginacion,
  Saldos,
  Select,
  Tabla,
  Tarjeta,
  Td,
  Th,
  Vacio,
} from "../components/ui";
import { api } from "../lib/api";
import { useFiltros } from "../lib/filtros";
import { useEmpresasCatalogo } from "../lib/queries";
import type { Pagina, Proyecto } from "../lib/types";

const LIMITE = 50;
const CLAVES = ["q", "empresa_id", "activo"] as const;

export default function Proyectos() {
  const navigate = useNavigate();
  const { filtros, offset, cambiar } = useFiltros(CLAVES);
  const [nuevo, setNuevo] = useState(false);
  const empresas = useEmpresasCatalogo();

  const { data, isLoading, error } = useQuery({
    queryKey: ["proyectos", "lista", filtros, offset],
    queryFn: () => api.get<Pagina<Proyecto>>("/proyectos", { ...filtros, limit: LIMITE, offset }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <EncabezadoPagina
        titulo="Proyectos"
        descripcion="Un proyecto puede estar en una o varias empresas. Su saldo es lo que entró (neto) menos lo que salió."
        acciones={<Boton onClick={() => setNuevo(true)}><Icono nombre="mas" className="size-4" /> Nuevo proyecto</Boton>}
      />

      <Tarjeta className="mb-4 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Campo etiqueta="Buscar">
            {(id) => <Input id={id} type="search" value={filtros.q} onChange={(e) => cambiar({ q: e.target.value })} placeholder="Nombre" />}
          </Campo>
          <Campo etiqueta="Empresa">
            {(id) => (
              <Select id={id} value={filtros.empresa_id} onChange={(e) => cambiar({ empresa_id: e.target.value })}>
                <option value="">Todas</option>
                {empresas.data?.map((e) => <option key={e.id} value={e.id}>{e.nombre}</option>)}
              </Select>
            )}
          </Campo>
          <Campo etiqueta="Estado">
            {(id) => (
              <Select id={id} value={filtros.activo} onChange={(e) => cambiar({ activo: e.target.value })}>
                <option value="">Todos</option>
                <option value="true">Activos</option>
                <option value="false">Desactivados</option>
              </Select>
            )}
          </Campo>
        </div>
      </Tarjeta>

      <ErrorApi error={error} className="mb-4" />
      <Tarjeta>
        {isLoading ? (
          <Cargando />
        ) : !data?.items.length ? (
          <Vacio titulo="No hay proyectos" descripcion="Da de alta el primero; solo necesitas el nombre."
            accion={<Boton onClick={() => setNuevo(true)}>Nuevo proyecto</Boton>} />
        ) : (
          <>
            <Tabla>
              <thead>
                <tr>
                  <Th>Proyecto</Th>
                  <Th>Empresas</Th>
                  <Th derecha>Saldo</Th>
                  <Th>Registrado por</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {data.items.map((p) => (
                  <tr key={p.id} className="cursor-pointer hover:bg-neutral-50" onClick={() => navigate(`/proyectos/${p.id}`)}>
                    <Td>
                      <Link to={`/proyectos/${p.id}`} className="font-medium text-black hover:underline">{p.nombre}</Link>
                      {!p.activo && <span className="ml-2"><Insignia tono="tenue">Desactivado</Insignia></span>}
                    </Td>
                    <Td className="text-neutral-600">{p.empresas.map((e) => e.nombre).join(", ") || "—"}</Td>
                    <Td derecha><Saldos saldos={p.saldos} /></Td>
                    <Td className="text-neutral-500">{p.creado_por_nombre}</Td>
                  </tr>
                ))}
              </tbody>
            </Tabla>
            <Paginacion total={data.total} limit={LIMITE} offset={offset} onCambiar={(o) => cambiar({ offset: o })} />
          </>
        )}
      </Tarjeta>

      <ProyectoForm abierto={nuevo} onCerrar={() => setNuevo(false)} onCreado={(p) => navigate(`/proyectos/${p.id}`)} />
    </>
  );
}
