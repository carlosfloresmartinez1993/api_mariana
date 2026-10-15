import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { api, guardarBlob } from "../lib/api";
import { fecha } from "../lib/format";
import { useCategorias, useCuentas, useEmpresasCatalogo, useInvalidarDinero } from "../lib/queries";
import { NOMBRE_TIPO, type Cuenta, type Moneda, type Proyecto } from "../lib/types";
import { Icono } from "./Icono";
import { useToast } from "./Toast";
import { Aviso, Boton, Campo, Casilla, ErrorApi, Input, Modal, Monto, PieModal, Select, Tabla, Td, Th } from "./ui";

interface ErrorFila {
  fila: number | null;
  columna: string | null;
  mensaje: string;
}

interface CuentaPrevia {
  nombre: string;
  moneda: Moneda;
  forma: string;
}

interface VistaPrevia {
  valido: boolean;
  errores: ErrorFila[];
  entradas: number;
  salidas: number;
  entradas_bruto: string;
  entradas_gasto: string;
  entradas_neto: string;
  total_salidas: string;
  cuenta_entradas: CuentaPrevia;
  cuenta_salidas: CuentaPrevia;
  categoria_entradas: string | null;
  categoria_salidas: string | null;
  saldos: { cuenta: string; moneda: Moneda; antes: string; despues: string }[];
  filas: { fila: number; fecha: string; concepto: string | null; tipo: "entrada" | "salida"; monto: string }[];
}

type Paso = "requisitos" | "datos" | "previa";

function Requisito({ cumplido, opcional, children }: { cumplido: boolean; opcional?: boolean; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2">
      <span aria-hidden className={`mt-0.5 inline-flex size-5 shrink-0 items-center justify-center rounded-full text-xs font-bold ring-1 ${
        cumplido ? "bg-black text-white ring-black" : "bg-white text-black ring-neutral-400"}`}>
        {cumplido ? "✓" : opcional ? "–" : "!"}
      </span>
      <span>{children}</span>
    </li>
  );
}

function nombreCuenta(c: Cuenta) {
  return `${c.nombre} · ${NOMBRE_TIPO[c.tipo]} ${c.moneda}`;
}

/**
 * Carga masiva desde el Excel del cliente (FECHA, CONCEPTO, CARGO, ABONO).
 * ABONO = entrada, CARGO = salida. Primero muestra lo que debe existir, luego se eligen empresa y cuentas,
 * se revisa la vista previa y solo al confirmar se registra todo (primero entradas, después salidas).
 */
export function CargaMasiva({ abierto, proyecto, onCerrar }: { abierto: boolean; proyecto: Proyecto; onCerrar: () => void }) {
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const empresas = useEmpresasCatalogo();
  const cuentas = useCuentas();
  const categorias = useCategorias();

  const [paso, setPaso] = useState<Paso>("requisitos");
  const [empresaId, setEmpresaId] = useState("");
  const [cuentaEntradas, setCuentaEntradas] = useState("");
  const [cuentaSalidas, setCuentaSalidas] = useState("");
  const [porcentaje, setPorcentaje] = useState("");
  const [categoriaEntradas, setCategoriaEntradas] = useState("");
  const [categoriaSalidas, setCategoriaSalidas] = useState("");
  const [facturaEntradas, setFacturaEntradas] = useState(false);
  const [facturaSalidas, setFacturaSalidas] = useState(false);
  const [archivo, setArchivo] = useState<File | null>(null);
  const [previa, setPrevia] = useState<VistaPrevia | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  const activas = useMemo(() => (cuentas.data ?? []).filter((c) => c.activa), [cuentas.data]);
  const empresasConCuentas = (empresas.data ?? []).filter((e) => e.activa && activas.some((c) => c.empresa_id === e.id));
  const vinculadas = empresasConCuentas.filter((e) => proyecto.empresas.some((x) => x.id === e.id));
  const cuentasEmpresa = activas.filter((c) => c.empresa_id === empresaId);
  const categoriasActivas = (categorias.data ?? []).filter((c) => c.activa);
  const listo = proyecto.activo && empresasConCuentas.length > 0;

  useEffect(() => {
    if (!abierto) return;
    setPaso("requisitos");
    setArchivo(null);
    setPrevia(null);
    setError(null);
  }, [abierto]);

  useEffect(() => {
    // Si el proyecto ya tiene una sola empresa con cuentas, se propone esa.
    if (abierto && !empresaId && vinculadas.length === 1) setEmpresaId(vinculadas[0].id);
  }, [abierto, empresaId, vinculadas]);

  function cambiarEmpresa(id: string) {
    setEmpresaId(id);
    setCuentaEntradas("");
    setCuentaSalidas("");
  }

  function formulario() {
    const datos = new FormData();
    datos.append("archivo", archivo!);
    datos.append("empresa_id", empresaId);
    datos.append("cuenta_entradas_id", cuentaEntradas);
    datos.append("cuenta_salidas_id", cuentaSalidas);
    datos.append("porcentaje_gasto", porcentaje.trim() || "0");
    if (categoriaEntradas) datos.append("categoria_entradas_id", categoriaEntradas);
    if (categoriaSalidas) datos.append("categoria_salidas_id", categoriaSalidas);
    datos.append("requiere_factura_entradas", String(facturaEntradas));
    datos.append("requiere_factura_salidas", String(facturaSalidas));
    return datos;
  }

  async function revisar(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      setPrevia(await api.postForm<VistaPrevia>(`/proyectos/${proyecto.id}/carga-masiva/vista-previa`, formulario()));
      setPaso("previa");
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  async function confirmar() {
    setError(null);
    setEnviando(true);
    try {
      const r = await api.postForm<{ entradas: number; salidas: number }>(`/proyectos/${proyecto.id}/carga-masiva`, formulario());
      await invalidar();
      avisar(`Carga terminada: ${r.entradas} entradas y ${r.salidas} salidas registradas`);
      onCerrar();
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  async function descargarPlantilla() {
    try {
      guardarBlob(await api.blob("/carga-masiva/plantilla"), "plantilla-carga-masiva.xlsx");
    } catch (err) {
      avisar((err as Error).message, "error");
    }
  }

  return (
    <Modal abierto={abierto} onCerrar={onCerrar} ancho={paso === "previa" ? "xl" : "lg"}
      titulo={`Carga masiva · ${proyecto.nombre}`}
      descripcion={{ requisitos: "Paso 1 de 3: lo que debe existir antes", datos: "Paso 2 de 3: dónde se registra",
        previa: "Paso 3 de 3: revisa y confirma" }[paso]}>
      {paso === "requisitos" && (
        <div className="space-y-4 text-sm">
          <Aviso tono="aviso" titulo="Antes de cargar el Excel">
            El archivo no trae empresa ni cuentas: se eligen en el siguiente paso, así que deben estar dados de alta.
          </Aviso>
          <ul className="space-y-2">
            <Requisito cumplido={proyecto.activo}>El proyecto está activo.</Requisito>
            <Requisito cumplido={empresasConCuentas.length > 0}>
              La <b>empresa</b> a la que va el proyecto, con sus <b>cuentas</b> activas: una cuenta de banco para
              transferencias o la caja para efectivo, en la moneda correcta (MXN o USD).{" "}
              {empresasConCuentas.length > 0
                ? <span className="text-neutral-500">Hay {empresasConCuentas.length} empresa(s) con cuentas.</span>
                : <Link to="/empresas" className="font-medium underline">Dar de alta empresa y cuentas</Link>}
            </Requisito>
            <Requisito cumplido opcional>
              El proyecto no necesita estar vinculado a la empresa: se vincula solo al cargar.
              {proyecto.empresas.length > 0 && <span className="text-neutral-500"> Ya vinculado a: {proyecto.empresas.map((e) => e.nombre).join(", ")}.</span>}
            </Requisito>
            <Requisito cumplido={categoriasActivas.length > 0} opcional>
              Opcional: las <b>categorías</b> que quieras asignar a las entradas y a las salidas.{" "}
              <Link to="/categorias" className="underline">{categoriasActivas.length > 0 ? `${categoriasActivas.length} activas` : "Crear categorías"}</Link>
            </Requisito>
            <Requisito cumplido opcional>
              Si las salidas superan lo que hay en la cuenta, se rechaza toda la carga: la cuenta no puede quedar en negativo.
            </Requisito>
          </ul>
          <div className="rounded-md p-3 ring-1 ring-neutral-200">
            <p className="font-semibold text-black">Formato del Excel</p>
            <p className="mt-1 text-neutral-600">
              Primera hoja con las columnas <b>FECHA</b>, <b>CONCEPTO</b>, <b>CARGO</b> y <b>ABONO</b>.
              Los <b>abonos</b> son entradas y los <b>cargos</b> son salidas; cada fila lleva uno de los dos.
              Si una fila tiene un error no se registra nada.
            </p>
            <Boton variante="secundario" tamano="sm" className="mt-2" onClick={descargarPlantilla}>
              <Icono nombre="descargar" className="size-4" /> Descargar plantilla
            </Boton>
          </div>
          <PieModal>
            <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
            <Boton disabled={!listo} onClick={() => setPaso("datos")}>Ya los tengo, continuar</Boton>
          </PieModal>
        </div>
      )}

      {paso === "datos" && (
        <form onSubmit={revisar} className="space-y-4">
          <Campo etiqueta="Empresa" requerido ayuda="Solo aparecen empresas activas con cuentas.">
            {(id) => (
              <Select id={id} required value={empresaId} onChange={(e) => cambiarEmpresa(e.target.value)}>
                <option value="">Elige la empresa…</option>
                {empresasConCuentas.map((e) => <option key={e.id} value={e.id}>{e.nombre}</option>)}
              </Select>
            )}
          </Campo>
          {empresaId && (
            <div className="rounded-md ring-1 ring-neutral-200">
              <Tabla>
                <thead><tr><Th>Cuentas de la empresa</Th><Th>Tipo</Th><Th>Moneda</Th><Th derecha>Saldo actual</Th></tr></thead>
                <tbody className="divide-y divide-neutral-100">
                  {cuentasEmpresa.map((c) => (
                    <tr key={c.id}><Td>{c.nombre}</Td><Td>{NOMBRE_TIPO[c.tipo]}</Td><Td>{c.moneda}</Td><Td derecha><Monto valor={c.saldo} /></Td></tr>
                  ))}
                </tbody>
              </Tabla>
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <fieldset className="space-y-3 rounded-md p-3 ring-1 ring-neutral-200">
              <legend className="px-1 text-sm font-semibold text-black">Entradas (ABONO)</legend>
              <Campo etiqueta="Cuenta donde entra" requerido>
                {(id) => (
                  <Select id={id} required value={cuentaEntradas} disabled={!empresaId} onChange={(e) => setCuentaEntradas(e.target.value)}>
                    <option value="">Elige…</option>
                    {cuentasEmpresa.map((c) => <option key={c.id} value={c.id}>{nombreCuenta(c)}</option>)}
                  </Select>
                )}
              </Campo>
              <Campo etiqueta="% de gasto" ayuda="Se descuenta de cada abono; la cuenta recibe el neto.">
                {(id) => <Input id={id} inputMode="decimal" value={porcentaje} onChange={(e) => setPorcentaje(e.target.value)} placeholder="0" />}
              </Campo>
              <Campo etiqueta="Categoría">
                {(id) => (
                  <Select id={id} value={categoriaEntradas} onChange={(e) => setCategoriaEntradas(e.target.value)}>
                    <option value="">Sin categoría</option>
                    {categoriasActivas.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
                  </Select>
                )}
              </Campo>
              <Casilla checked={facturaEntradas} onChange={setFacturaEntradas}>Requieren factura</Casilla>
            </fieldset>
            <fieldset className="space-y-3 rounded-md p-3 ring-1 ring-neutral-200">
              <legend className="px-1 text-sm font-semibold text-black">Salidas (CARGO)</legend>
              <Campo etiqueta="Cuenta de donde sale" requerido>
                {(id) => (
                  <Select id={id} required value={cuentaSalidas} disabled={!empresaId} onChange={(e) => setCuentaSalidas(e.target.value)}>
                    <option value="">Elige…</option>
                    {cuentasEmpresa.map((c) => <option key={c.id} value={c.id}>{nombreCuenta(c)}</option>)}
                  </Select>
                )}
              </Campo>
              <Campo etiqueta="Categoría">
                {(id) => (
                  <Select id={id} value={categoriaSalidas} onChange={(e) => setCategoriaSalidas(e.target.value)}>
                    <option value="">Sin categoría</option>
                    {categoriasActivas.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
                  </Select>
                )}
              </Campo>
              <Casilla checked={facturaSalidas} onChange={setFacturaSalidas}>Requieren factura</Casilla>
            </fieldset>
          </div>
          <Campo etiqueta="Archivo de Excel (.xlsx)" requerido>
            {(id) => (
              <input id={id} type="file" required accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
                className="block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-black file:px-3 file:py-1.5 file:text-white" />
            )}
          </Campo>
          <ErrorApi error={error} />
          <PieModal>
            <Boton variante="secundario" onClick={() => setPaso("requisitos")}>Atrás</Boton>
            <Boton type="submit" disabled={enviando || !archivo}>{enviando ? "Revisando…" : "Ver vista previa"}</Boton>
          </PieModal>
        </form>
      )}

      {paso === "previa" && previa && (
        <div className="space-y-4 text-sm">
          {!previa.valido ? (
            <>
              <Aviso tono="peligro" titulo="El archivo tiene errores: no se registrará nada">
                Corrige el Excel y vuelve a cargarlo.
              </Aviso>
              <div className="rounded-md ring-1 ring-neutral-200">
                <Tabla>
                  <thead><tr><Th>Fila</Th><Th>Columna</Th><Th>Error</Th></tr></thead>
                  <tbody className="divide-y divide-neutral-100">
                    {previa.errores.map((e, i) => (
                      <tr key={i}><Td>{e.fila ?? "—"}</Td><Td>{e.columna ?? "—"}</Td><Td>{e.mensaje}</Td></tr>
                    ))}
                  </tbody>
                </Tabla>
              </div>
            </>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-md p-3 ring-1 ring-neutral-200">
                  <p className="font-semibold text-black">{previa.entradas} entradas → {previa.cuenta_entradas.nombre} ({previa.cuenta_entradas.moneda})</p>
                  <p className="text-neutral-600">Bruto <Monto valor={previa.entradas_bruto} /> · gasto <Monto valor={previa.entradas_gasto} /> · neto <b><Monto valor={previa.entradas_neto} /></b></p>
                  <p className="text-neutral-500">{previa.cuenta_entradas.forma} · {previa.categoria_entradas ?? "sin categoría"}</p>
                </div>
                <div className="rounded-md p-3 ring-1 ring-neutral-200">
                  <p className="font-semibold text-black">{previa.salidas} salidas ← {previa.cuenta_salidas.nombre} ({previa.cuenta_salidas.moneda})</p>
                  <p className="text-neutral-600">Total <b><Monto valor={previa.total_salidas} /></b></p>
                  <p className="text-neutral-500">{previa.cuenta_salidas.forma} · {previa.categoria_salidas ?? "sin categoría"}</p>
                </div>
              </div>
              <div className="rounded-md ring-1 ring-neutral-200">
                <Tabla>
                  <thead><tr><Th>Cuenta</Th><Th>Moneda</Th><Th derecha>Saldo antes</Th><Th derecha>Saldo después</Th></tr></thead>
                  <tbody className="divide-y divide-neutral-100">
                    {previa.saldos.map((s) => (
                      <tr key={s.cuenta}><Td>{s.cuenta}</Td><Td>{s.moneda}</Td><Td derecha><Monto valor={s.antes} /></Td><Td derecha className="font-semibold"><Monto valor={s.despues} /></Td></tr>
                    ))}
                  </tbody>
                </Tabla>
              </div>
              <p className="text-neutral-500">Se registrarán en este orden: primero las entradas y después las salidas.</p>
              <div className="max-h-80 overflow-y-auto rounded-md ring-1 ring-neutral-200">
                <Tabla>
                  <thead><tr><Th>Fila</Th><Th>Tipo</Th><Th>Fecha</Th><Th>Concepto</Th><Th derecha>Monto</Th></tr></thead>
                  <tbody className="divide-y divide-neutral-100">
                    {previa.filas.map((f) => (
                      <tr key={f.fila}>
                        <Td>{f.fila}</Td>
                        <Td>{f.tipo === "entrada" ? "Entrada (abono)" : "Salida (cargo)"}</Td>
                        <Td>{fecha(f.fecha)}</Td>
                        <Td>{f.concepto ?? "—"}</Td>
                        <Td derecha><Monto valor={f.monto} /></Td>
                      </tr>
                    ))}
                  </tbody>
                </Tabla>
              </div>
            </>
          )}
          <ErrorApi error={error} />
          <PieModal>
            <Boton variante="secundario" onClick={() => setPaso("datos")}>Atrás</Boton>
            {previa.valido && (
              <Boton disabled={enviando} onClick={confirmar}>
                {enviando ? "Registrando…" : `Confirmar carga (${previa.entradas + previa.salidas} movimientos)`}
              </Boton>
            )}
          </PieModal>
        </div>
      )}
    </Modal>
  );
}
