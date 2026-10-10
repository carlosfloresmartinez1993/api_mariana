import { useState } from "react";
import { api, guardarBlob, type Query } from "../lib/api";
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
  if (texto === "transferencia" || texto === "efectivo") return { texto: texto[0].toUpperCase() + texto.slice(1), numerica: false, negativa: false };
  return { texto, numerica: false, negativa: false };
}

/** Tabla genérica para cualquier reporte del backend: columnas, filas y una fila de totales por moneda. */
export function ReporteTabla({ reporte }: { reporte: Reporte }) {
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
              return <Td key={c.clave} derecha={v.numerica} className={v.negativa ? "font-semibold" : undefined}>{v.texto}</Td>;
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
                return <Td key={c.clave} derecha={v.numerica} className="text-black">{v.texto}</Td>;
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
