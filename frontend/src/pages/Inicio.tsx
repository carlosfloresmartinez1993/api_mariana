import { useState } from "react";
import { Link } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { EntradaForm, SalidaForm } from "../components/formularios/MovimientoForms";
import { Icono } from "../components/Icono";
import { Boton, Cargando, EncabezadoPagina, ErrorApi, Monto, Tabla, Tarjeta, Td, Th, Vacio } from "../components/ui";
import { api } from "../lib/api";
import { useProyectosCatalogo } from "../lib/queries";
import type { Resumen } from "../lib/types";

export default function Inicio() {
  const { usuario } = useAuth();
  const [abierto, setAbierto] = useState<"entrada" | "salida" | null>(null);
  const resumen = useQuery({ queryKey: ["resumen"], queryFn: () => api.get<Resumen>("/reportes/resumen") });
  const proyectos = useProyectosCatalogo();
  const conSaldo = (proyectos.data ?? []).filter((p) => p.saldos.length > 0);

  return (
    <>
      <EncabezadoPagina
        titulo={`Hola, ${usuario?.nombre ?? ""}`}
        descripcion="Dinero disponible en cajas y bancos, y saldo de cada proyecto."
        acciones={
          <>
            <Boton onClick={() => setAbierto("entrada")}><Icono nombre="entradas" className="size-4" /> Entrada</Boton>
            <Boton variante="secundario" onClick={() => setAbierto("salida")}><Icono nombre="salidas" className="size-4" /> Salida</Boton>
          </>
        }
      />

      <ErrorApi error={resumen.error} className="mb-4" />
      {resumen.isLoading ? (
        <Cargando />
      ) : (
        <div className="mb-8 grid gap-4 md:grid-cols-2">
          {resumen.data?.dinero.length ? (
            resumen.data.dinero.map((d) => (
              <Tarjeta key={d.moneda} className="p-5">
                <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Disponible en {d.moneda}</p>
                <p className="mt-1 text-3xl font-semibold tracking-tight text-black"><Monto valor={d.total} moneda={d.moneda} /></p>
                <div className="mt-4 grid grid-cols-2 gap-3 border-t border-neutral-200 pt-3 text-sm">
                  <div><p className="text-neutral-500">Cajas</p><Monto valor={d.cajas} /></div>
                  <div><p className="text-neutral-500">Bancos</p><Monto valor={d.bancos} /></div>
                </div>
              </Tarjeta>
            ))
          ) : (
            <Tarjeta className="p-5 md:col-span-2">
              <p className="text-sm text-neutral-700">
                Aún no hay cuentas. Empieza por dar de alta una <Link to="/empresas" className="font-medium underline">empresa</Link> y
                sus cuentas de banco o cajas.
              </p>
            </Tarjeta>
          )}
        </div>
      )}

      <div className="mb-3 flex items-end justify-between">
        <h2 className="text-lg font-semibold text-black">Saldo por proyecto</h2>
        <Link to="/proyectos" className="text-sm font-medium underline">Ver proyectos</Link>
      </div>
      <Tarjeta>
        {proyectos.isLoading ? (
          <Cargando />
        ) : !conSaldo.length ? (
          <Vacio titulo="Sin movimientos todavía" descripcion="Cuando registres entradas, aquí verás el saldo de cada proyecto." />
        ) : (
          <Tabla>
            <thead>
              <tr>
                <Th>Proyecto</Th>
                <Th>Moneda</Th>
                <Th derecha>Ingresos (neto)</Th>
                <Th derecha>Gastos</Th>
                <Th derecha>Salidas</Th>
                <Th derecha>Saldo</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {conSaldo.flatMap((p) =>
                p.saldos.map((s, i) => (
                  <tr key={`${p.id}-${s.moneda}`} className="hover:bg-neutral-50">
                    <Td>{i === 0 && <Link to={`/proyectos/${p.id}`} className="font-medium text-black hover:underline">{p.nombre}</Link>}</Td>
                    <Td>{s.moneda}</Td>
                    <Td derecha><Monto valor={s.ingresos} /></Td>
                    <Td derecha><Monto valor={s.gastos} /></Td>
                    <Td derecha><Monto valor={s.salidas} /></Td>
                    <Td derecha className="font-semibold text-black"><Monto valor={s.saldo} /></Td>
                  </tr>
                )),
              )}
            </tbody>
          </Tabla>
        )}
      </Tarjeta>

      <EntradaForm abierto={abierto === "entrada"} onCerrar={() => setAbierto(null)} />
      <SalidaForm abierto={abierto === "salida"} onCerrar={() => setAbierto(null)} />
    </>
  );
}
