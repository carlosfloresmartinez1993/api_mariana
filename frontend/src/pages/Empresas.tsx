import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { EmpresaForm } from "../components/formularios/NombreForm";
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
import type { Empresa, Pagina } from "../lib/types";

const LIMITE = 50;
const CLAVES = ["q", "activa"] as const;

export default function Empresas() {
  const navigate = useNavigate();
  const { filtros, offset, cambiar } = useFiltros(CLAVES);
  const [nueva, setNueva] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["empresas", "lista", filtros, offset],
    queryFn: () => api.get<Pagina<Empresa>>("/empresas", { ...filtros, limit: LIMITE, offset }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <EncabezadoPagina
        titulo="Empresas"
        descripcion="Cada empresa tiene sus cuentas de banco y sus cajas de efectivo, en pesos o en dólares."
        acciones={<Boton onClick={() => setNueva(true)}><Icono nombre="mas" className="size-4" /> Nueva empresa</Boton>}
      />

      <Tarjeta className="mb-4 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Campo etiqueta="Buscar">
            {(id) => <Input id={id} type="search" value={filtros.q} onChange={(e) => cambiar({ q: e.target.value })} placeholder="Nombre" />}
          </Campo>
          <Campo etiqueta="Estado">
            {(id) => (
              <Select id={id} value={filtros.activa} onChange={(e) => cambiar({ activa: e.target.value })}>
                <option value="">Todas</option>
                <option value="true">Activas</option>
                <option value="false">Desactivadas</option>
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
          <Vacio titulo="No hay empresas" descripcion="Da de alta la primera; solo necesitas el nombre."
            accion={<Boton onClick={() => setNueva(true)}>Nueva empresa</Boton>} />
        ) : (
          <>
            <Tabla>
              <thead>
                <tr>
                  <Th>Empresa</Th>
                  <Th derecha>Cuentas</Th>
                  <Th derecha>Proyectos</Th>
                  <Th derecha>Saldo</Th>
                  <Th>Registrada por</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {data.items.map((e) => (
                  <tr key={e.id} className="cursor-pointer hover:bg-neutral-50" onClick={() => navigate(`/empresas/${e.id}`)}>
                    <Td>
                      <Link to={`/empresas/${e.id}`} className="font-medium text-black hover:underline">{e.nombre}</Link>
                      {!e.activa && <span className="ml-2"><Insignia tono="tenue">Desactivada</Insignia></span>}
                    </Td>
                    <Td derecha>{e.num_cuentas}</Td>
                    <Td derecha>{e.num_proyectos}</Td>
                    <Td derecha><Saldos saldos={e.saldos} /></Td>
                    <Td className="text-neutral-500">{e.creado_por_nombre}</Td>
                  </tr>
                ))}
              </tbody>
            </Tabla>
            <Paginacion total={data.total} limit={LIMITE} offset={offset} onCambiar={(o) => cambiar({ offset: o })} />
          </>
        )}
      </Tarjeta>

      <EmpresaForm abierto={nueva} onCerrar={() => setNueva(false)} onCreada={(e) => navigate(`/empresas/${e.id}`)} />
    </>
  );
}
