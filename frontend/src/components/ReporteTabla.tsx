import { useState } from "react";
import { api, guardarBlob, type Query } from "../lib/api";
import { cn } from "../lib/cn";
import { fecha, numero, porcentaje } from "../lib/format";
import type { Reporte } from "../lib/types";
import { Icono } from "./Icono";
import { useToast } from "./Toast";
import { Boton, Tabla, Td, Th, Vacio } from "./ui";

const MONTO = /^-?\d+\.\d{2}$/;
const FECHA = /^\d{4}-\d{2}-\d{2}$/;

function celda(clave: string, valor: unknown): { texto: string; numerica: boolean; negativa: boolean } {
  if (valor === null || valor === undefined || valor === "") return { texto: "", numerica: false, negativa: false };
  if (typeof valor === "number") return { texto: String(valor), numerica: true, negativa: false };
  const texto = String(valor);
  if (clave === "porcentaje") return { texto: porcentaje(texto), numerica: true, negativa: false };
  if (MONTO.test(texto)) {
    const n = Number(texto);
    return { texto: n < 0 ? `(${numero(-n)})` : numero(n), numerica: true, negativa: n < 0 };
  }
  if (FECHA.test(texto)) return { texto: fecha(texto), numerica: false, negativa: false };
  if (texto === "NO CUADRA") return { texto, numerica: false, negativa: true };
  if (texto === "transferencia" || texto === "efectivo") return { texto: texto[0].toUpperCase() + texto.slice(1), numerica: false, negativa: false };
  return { texto, numerica: false, negativa: false };
}

/**
 * Estado de ingresos y egresos (como el formato de Excel del usuario): encabezado azul marino, ingresos en verde,
 * totales sombreados y resultado neto en azul marino. Es el único reporte con color además del rojo.
 */
function ResumenTabla({ reporte }: { reporte: Reporte }) {
  const monedas = reporte.columnas.filter((c) => c.clave !== "concepto");
  const monto = (valor: unknown, estilo: string) => {
    if (valor === null || valor === undefined) return "";
    const n = Number(valor);
    if (n === 0) return estilo === "ingreso" || estilo === "egreso" ? "" : "-";
    return n < 0 ? `(${numero(-n)})` : numero(n);
  };
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="bg-[#0E1A33] text-white">
            <th className="px-4 py-2.5 text-left font-semibold">Concepto</th>
            {monedas.map((m) => <th key={m.clave} className="w-40 px-4 py-2.5 text-right font-semibold">{m.etiqueta}</th>)}
          </tr>
        </thead>
        <tbody>
          {reporte.filas.map((f, i) => {
            const estilo = String(f.estilo);
            const negativo = (m: { clave: string }) => Number(f[m.clave] ?? 0) < 0;
            if (estilo === "seccion") {
              return (
                <tr key={i}>
                  <td colSpan={monedas.length + 1} className="px-4 pt-5 pb-1 text-base font-bold text-[#0E1A33]">{String(f.concepto)}</td>
                </tr>
              );
            }
            if (estilo === "ingreso" || estilo === "egreso") {
              return (
                <tr key={i} className="border-b border-neutral-200 hover:bg-neutral-50">
                  <td className="px-4 py-1.5">
                    <p className="text-black">{String(f.concepto)}</p>
                    {f.detalle ? <p className="text-xs text-neutral-500">{String(f.detalle)}</p> : null}
                  </td>
                  {monedas.map((m) => (
                    <td key={m.clave} className={cn("px-4 py-1.5 text-right tabular-nums",
                      negativo(m) ? "font-semibold text-red-600" : estilo === "ingreso" ? "text-green-700" : "text-black")}>
                      {monto(f[m.clave], estilo)}
                    </td>
                  ))}
                </tr>
              );
            }
            if (estilo === "resultado") {
              return (
                <tr key={i} className="border-t-[12px] border-white bg-[#0E1A33] font-bold text-white">
                  <td className="px-4 py-2.5">{String(f.concepto)}</td>
                  {monedas.map((m) => (
                    <td key={m.clave} className={cn("px-4 py-2.5 text-right tabular-nums", negativo(m) && "text-red-300")}>
                      {monto(f[m.clave], estilo)}
                    </td>
                  ))}
                </tr>
              );
            }
            return (
              <tr key={i} className="border-t-2 border-[#0E1A33] bg-[#F2F0EB] font-bold text-black">
                <td className="px-4 py-2">{String(f.concepto)}</td>
                {monedas.map((m) => (
                  <td key={m.clave} className={cn("px-4 py-2 text-right tabular-nums", negativo(m) && "text-red-600")}>
                    {monto(f[m.clave], estilo)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Tabla genérica para cualquier reporte del backend: columnas, filas y una fila de totales por moneda. */
export function ReporteTabla({ reporte }: { reporte: Reporte }) {
  if (reporte.estilo === "resumen") return <ResumenTabla reporte={reporte} />;
  if (!reporte.filas.length) return <Vacio titulo="Sin movimientos" descripcion="No hay datos con esos filtros." />;
  return (
    <Tabla>
      <thead>
        <tr>
          {reporte.columnas.map((c) => {
            const numerica = reporte.filas.some((f) => celda(c.clave, f[c.clave]).numerica);
            return <Th key={c.clave} derecha={numerica}>{c.etiqueta}</Th>;
          })}
        </tr>
      </thead>
      <tbody className="divide-y divide-neutral-100">
        {reporte.filas.map((f, i) => (
          <tr key={i} className={f.tipo === "Saldo anterior" ? "bg-neutral-50 italic" : "hover:bg-neutral-50"}>
            {reporte.columnas.map((c) => {
              const v = celda(c.clave, f[c.clave]);
              return <Td key={c.clave} derecha={v.numerica} className={v.negativa ? "font-semibold text-red-600!" : undefined}>{v.texto}</Td>;
            })}
          </tr>
        ))}
      </tbody>
      {reporte.totales.length > 0 && (
        <tfoot className="border-t-2 border-black">
          {reporte.totales.map((t, i) => (
            <tr key={i} className="font-semibold">
              {reporte.columnas.map((c) => {
                const v = celda(c.clave, t[c.clave]);
                return <Td key={c.clave} derecha={v.numerica} className={v.negativa ? "text-red-600!" : "text-black"}>{v.texto}</Td>;
              })}
            </tr>
          ))}
        </tfoot>
      )}
    </Tabla>
  );
}

/** Botones para descargar el reporte en Excel, PDF o CSV. */
export function Exportar({ ruta, query, nombre }: { ruta: string; query: Query; nombre: string }) {
  const avisar = useToast();
  const [bajando, setBajando] = useState<string | null>(null);

  async function bajar(formato: "xlsx" | "pdf" | "csv") {
    setBajando(formato);
    try {
      guardarBlob(await api.blob(ruta, { ...query, formato }), `${nombre}.${formato}`);
    } catch (e) {
      avisar((e as Error).message, "error");
    } finally {
      setBajando(null);
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      {(["xlsx", "pdf", "csv"] as const).map((f) => (
        <Boton key={f} variante="secundario" tamano="sm" cargando={bajando === f} onClick={() => bajar(f)}>
          <Icono nombre="descargar" className="size-4" /> {f === "xlsx" ? "Excel" : f.toUpperCase()}
        </Boton>
      ))}
    </div>
  );
}
