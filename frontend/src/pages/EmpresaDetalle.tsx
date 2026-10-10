import { useState } from "react";
import { Link, useParams } from "react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { CuentaForm } from "../components/formularios/CuentaForm";
import { EmpresaForm } from "../components/formularios/NombreForm";
import { Icono } from "../components/Icono";
import { useToast } from "../components/Toast";
import {
  Boton,
  Cargando,
  EncabezadoPagina,
  ErrorApi,
  Insignia,
  Monto,
  Saldos,
  Tabla,
  Tarjeta,
  Td,
  Th,
  Vacio,
} from "../components/ui";
import { api } from "../lib/api";
import { fecha } from "../lib/format";
import { useCuentas, useInvalidarDinero } from "../lib/queries";
import { MONEDAS, NOMBRE_TIPO, type Cuenta, type Empresa, type Pagina, type Proyecto } from "../lib/types";

export default function EmpresaDetalle() {
  const { id = "" } = useParams();
  const { puedeCorregir } = useAuth();
  const avisar = useToast();
  const qc = useQueryClient();
  const invalidar = useInvalidarDinero();
  const [editando, setEditando] = useState(false);
  const [cuentaForm, setCuentaForm] = useState<{ cuenta: Cuenta | null } | null>(null);

  const empresa = useQuery({ queryKey: ["empresas", id], queryFn: () => api.get<Empresa>(`/empresas/${id}`) });
  const cuentas = useCuentas(id);
  const proyectos = useQuery({
    queryKey: ["proyectos", "de-empresa", id],
    queryFn: () => api.get<Pagina<Proyecto>>("/proyectos", { empresa_id: id, limit: 500 }),
  });

  if (empresa.isLoading) return <Cargando />;
  if (empresa.error || !empresa.data) return <ErrorApi error={empresa.error} />;
  const e = empresa.data;
  const corregible = puedeCorregir(e);

  async function alternarEmpresa() {
    if (e.activa && !confirm(`¿Desactivar «${e.nombre}»? Ya no se podrá capturar en sus cuentas.`)) return;
    try {
      await api.post(`/empresas/${e.id}/${e.activa ? "desactivar" : "activar"}`);
      await qc.invalidateQueries({ queryKey: ["empresas"] });
      avisar(e.activa ? "Empresa desactivada" : "Empresa activada");
    } catch (err) {
      avisar((err as Error).message, "error");
    }
  }

  async function alternarCuenta(c: Cuenta) {
    try {
      await api.post(`/cuentas/${c.id}/${c.activa ? "desactivar" : "activar"}`);
      await invalidar();
      avisar(c.activa ? "Cuenta desactivada" : "Cuenta activada");
    } catch (err) {
      avisar((err as Error).message, "error");
    }
  }

  const lista = cuentas.data ?? [];
  const subtotales = MONEDAS.map((m) => {
    const deMoneda = lista.filter((c) => c.moneda === m);
    const suma = (tipo?: string) => deMoneda.filter((c) => !tipo || c.tipo === tipo).reduce((s, c) => s + Number(c.saldo), 0);
    return { moneda: m, hay: deMoneda.length > 0, cajas: suma("caja"), bancos: suma("banco"), total: suma() };
  }).filter((s) => s.hay);

  return (
    <>
      <Link to="/empresas" className="mb-3 inline-flex items-center gap-1 text-sm text-neutral-600 hover:text-black">
        <Icono nombre="flecha" className="size-4" /> Empresas
      </Link>
      <EncabezadoPagina
        titulo={<>{e.nombre} {!e.activa && <Insignia tono="tenue">Desactivada</Insignia>}</>}
        descripcion={`Registrada por ${e.creado_por_nombre} el ${fecha(e.fecha_creacion)}`}
        acciones={
          <>
            {e.activa && <Boton onClick={() => setCuentaForm({ cuenta: null })}><Icono nombre="mas" className="size-4" /> Cuenta o caja</Boton>}
            {corregible && <Boton variante="secundario" onClick={() => setEditando(true)}>Editar nombre</Boton>}
            {corregible && <Boton variante="secundario" onClick={alternarEmpresa}>{e.activa ? "Desactivar" : "Activar"}</Boton>}
          </>
        }
      />

      {subtotales.length > 0 && (
        <div className="mb-6 grid gap-4 md:grid-cols-2">
          {subtotales.map((s) => (
            <Tarjeta key={s.moneda} className="p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Total en {s.moneda}</p>
              <p className="mt-1 text-2xl font-semibold text-black"><Monto valor={s.total} moneda={s.moneda} /></p>
              <div className="mt-3 grid grid-cols-2 gap-3 border-t border-neutral-200 pt-3 text-sm">
                <div><p className="text-neutral-500">Caja</p><Monto valor={s.cajas} /></div>
                <div><p className="text-neutral-500">Bancos</p><Monto valor={s.bancos} /></div>
              </div>
            </Tarjeta>
          ))}
        </div>
      )}

      <h2 className="mb-3 text-lg font-semibold text-black">Cuentas</h2>
      <Tarjeta className="mb-8">
        {cuentas.isLoading ? (
          <Cargando />
        ) : !lista.length ? (
          <Vacio titulo="Sin cuentas" descripcion="Agrega cuentas de banco o cajas de efectivo cuando quieras. La moneda se elige al crearla y no cambia."
            accion={e.activa ? <Boton onClick={() => setCuentaForm({ cuenta: null })}>Agregar cuenta o caja</Boton> : undefined} />
        ) : (
          <Tabla>
            <thead>
              <tr>
                <Th>Cuenta</Th>
                <Th>Tipo</Th>
                <Th>Moneda</Th>
                <Th derecha>Saldo</Th>
                <Th><span className="sr-only">Acciones</span></Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {lista.map((c) => (
                <tr key={c.id} className={c.activa ? "hover:bg-neutral-50" : "text-neutral-400"}>
                  <Td>
                    <p className="font-medium text-black">{c.nombre} {!c.activa && <Insignia tono="tenue">Desactivada</Insignia>}</p>
                    {(c.banco || c.numero) && <p className="text-xs text-neutral-500">{[c.banco, c.numero].filter(Boolean).join(" · ")}</p>}
                  </Td>
                  <Td>{NOMBRE_TIPO[c.tipo]}</Td>
                  <Td>{c.moneda}</Td>
                  <Td derecha className="font-semibold text-black"><Monto valor={c.saldo} /></Td>
                  <Td className="whitespace-nowrap text-right">
                    <Link to={`/entradas?cuenta_id=${c.id}`} className="px-2 text-xs font-medium text-neutral-600 hover:text-black">Entradas</Link>
                    <Link to={`/salidas?cuenta_id=${c.id}`} className="px-2 text-xs font-medium text-neutral-600 hover:text-black">Salidas</Link>
                    {puedeCorregir(c) && (
                      <>
                        <Boton variante="fantasma" tamano="sm" onClick={() => setCuentaForm({ cuenta: c })}>Editar</Boton>
                        <Boton variante="fantasma" tamano="sm" onClick={() => alternarCuenta(c)}>{c.activa ? "Desactivar" : "Activar"}</Boton>
                      </>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Tabla>
        )}
      </Tarjeta>

      <h2 className="mb-3 text-lg font-semibold text-black">Proyectos</h2>
      <Tarjeta>
        {proyectos.isLoading ? (
          <Cargando />
        ) : !proyectos.data?.items.length ? (
          <Vacio titulo="Sin proyectos" descripcion="Los proyectos se vinculan solos al registrar una entrada o salida en esta empresa." />
        ) : (
          <Tabla>
            <thead>
              <tr>
                <Th>Proyecto</Th>
                <Th derecha>Saldo del proyecto (todas las empresas)</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {proyectos.data.items.map((p) => (
                <tr key={p.id} className="hover:bg-neutral-50">
                  <Td><Link to={`/proyectos/${p.id}`} className="font-medium text-black hover:underline">{p.nombre}</Link></Td>
                  <Td derecha><Saldos saldos={p.saldos} /></Td>
                </tr>
              ))}
            </tbody>
          </Tabla>
        )}
      </Tarjeta>

      <EmpresaForm abierto={editando} empresa={e} onCerrar={() => setEditando(false)} />
      <CuentaForm abierto={cuentaForm !== null} empresaId={e.id} cuenta={cuentaForm?.cuenta} onCerrar={() => setCuentaForm(null)} />
    </>
  );
}
