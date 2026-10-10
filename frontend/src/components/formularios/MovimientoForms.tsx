import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router";
import { api } from "../../lib/api";
import { calcularEntrada, dinero, hoyISO } from "../../lib/format";
import { useCuentas, useEmpresasCatalogo, useInvalidarDinero, useProyectosCatalogo } from "../../lib/queries";
import {
  NOMBRE_FORMA,
  TIPO_DE_FORMA,
  type Cuenta,
  type Entrada,
  type Forma,
  type Salida,
} from "../../lib/types";
import { useEnvio } from "../../lib/useEnvio";
import { useToast } from "../Toast";
import { Aviso, Boton, Campo, Dato, ErrorApi, Input, Modal, Opciones, PieModal, Select } from "../ui";

const FORMAS: { valor: Forma; texto: string }[] = [
  { valor: "transferencia", texto: "Transferencia" },
  { valor: "efectivo", texto: "Efectivo" },
];

function etiquetaCuenta(c: Cuenta) {
  return `${c.nombre} · ${c.moneda} · saldo ${dinero(c.saldo)}`;
}

// ------------------------------------------------------------------ selección compartida
interface Destino {
  proyectoId: string;
  empresaId: string;
  forma: Forma;
  cuentaId: string;
}

/** Proyecto → empresa → forma → cuenta. Las cuentas se filtran por empresa y por tipo (efectivo → caja). */
function useDestino(abierto: boolean, proyectoInicial?: string) {
  const [d, setD] = useState<Destino>({ proyectoId: "", empresaId: "", forma: "transferencia", cuentaId: "" });
  const proyectos = useProyectosCatalogo();
  const empresas = useEmpresasCatalogo();
  const cuentas = useCuentas();

  useEffect(() => {
    if (abierto) setD({ proyectoId: proyectoInicial ?? "", empresaId: "", forma: "transferencia", cuentaId: "" });
  }, [abierto, proyectoInicial]);

  const proyecto = proyectos.data?.find((p) => p.id === d.proyectoId);
  const empresa = empresas.data?.find((e) => e.id === d.empresaId);
  const opcionesCuenta = (cuentas.data ?? []).filter(
    (c) => c.activa && c.empresa_id === d.empresaId && c.tipo === TIPO_DE_FORMA[d.forma],
  );
  const cuenta = opcionesCuenta.find((c) => c.id === d.cuentaId);

  // Si solo hay una cuenta posible (p. ej. la caja de la única moneda), se elige sola.
  useEffect(() => {
    if (!cuenta && opcionesCuenta.length === 1) setD((x) => ({ ...x, cuentaId: opcionesCuenta[0].id }));
  }, [cuenta, opcionesCuenta]);

  const campos: ReactNode = (
    <>
      <Campo etiqueta="Proyecto" requerido>
        {(id) => (
          <Select id={id} required value={d.proyectoId} onChange={(e) => setD({ ...d, proyectoId: e.target.value })}>
            <option value="">Elige un proyecto…</option>
            {proyectos.data?.filter((p) => p.activo || p.id === d.proyectoId).map((p) => (
              <option key={p.id} value={p.id}>{p.nombre}</option>
            ))}
          </Select>
        )}
      </Campo>
      <Campo etiqueta="Empresa" requerido>
        {(id) => (
          <Select id={id} required value={d.empresaId} onChange={(e) => setD({ ...d, empresaId: e.target.value, cuentaId: "" })}>
            <option value="">Elige una empresa…</option>
            {proyecto && proyecto.empresas.length > 0 && (
              <optgroup label="Ya vinculadas al proyecto">
                {proyecto.empresas.filter((e) => e.activa).map((e) => <option key={e.id} value={e.id}>{e.nombre}</option>)}
              </optgroup>
            )}
            <optgroup label={proyecto?.empresas.length ? "Otras empresas" : "Empresas"}>
              {empresas.data?.filter((e) => e.activa && !proyecto?.empresas.some((x) => x.id === e.id)).map((e) => (
                <option key={e.id} value={e.id}>{e.nombre}</option>
              ))}
            </optgroup>
          </Select>
        )}
      </Campo>
      {proyecto && empresa && !proyecto.empresas.some((e) => e.id === empresa.id) && (
        <p className="text-xs text-neutral-600">
          «{empresa.nombre}» se vinculará automáticamente al proyecto «{proyecto.nombre}».
        </p>
      )}
      <Campo etiqueta="Forma">
        {() => <Opciones valor={d.forma} opciones={FORMAS} onCambiar={(forma) => setD({ ...d, forma, cuentaId: "" })} />}
      </Campo>
      <Campo etiqueta={d.forma === "efectivo" ? "Caja" : "Cuenta de banco"} requerido>
        {(id) => (
          <Select id={id} required value={d.cuentaId} disabled={!d.empresaId}
            onChange={(e) => setD({ ...d, cuentaId: e.target.value })}>
            <option value="">{d.empresaId ? "Elige…" : "Primero elige la empresa"}</option>
            {opcionesCuenta.map((c) => <option key={c.id} value={c.id}>{etiquetaCuenta(c)}</option>)}
          </Select>
        )}
      </Campo>
      {d.empresaId && !cuentas.isLoading && opcionesCuenta.length === 0 && (
        <Aviso tono="aviso">
          {empresa?.nombre} no tiene {d.forma === "efectivo" ? "caja" : "cuentas de banco"} activas.{" "}
          <Link to={`/empresas/${d.empresaId}`} className="font-medium underline">Agrégala en la empresa</Link>.
        </Aviso>
      )}
    </>
  );

  return { d, proyecto, cuenta, campos };
}

function useFechaMonto(abierto: boolean, inicial?: { fecha: string; monto: string }) {
  const [fecha, setFecha] = useState(hoyISO());
  const [monto, setMonto] = useState("");
  useEffect(() => {
    if (abierto) {
      setFecha(inicial?.fecha ?? hoyISO());
      setMonto(inicial?.monto ?? "");
    }
  }, [abierto, inicial]);
  return { fecha, setFecha, monto, setMonto };
}

/** Datos fijos de un movimiento que se está editando (no se pueden cambiar: se anula y se recaptura). */
function Fijos({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-3">
      <div className="grid gap-3 rounded-md bg-neutral-50 p-3 ring-1 ring-neutral-200 sm:grid-cols-2">{children}</div>
      <p className="text-xs text-neutral-500">Para cambiar el proyecto, la empresa o la cuenta, anula el movimiento y captúralo de nuevo.</p>
    </div>
  );
}

// ------------------------------------------------------------------ entrada
export function EntradaForm({ abierto, entrada, proyectoId, onCerrar }: {
  abierto: boolean;
  entrada?: Entrada | null;
  proyectoId?: string;
  onCerrar: () => void;
}) {
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const { error, enviando, enviar, limpiar } = useEnvio();
  const destino = useDestino(abierto && !entrada, proyectoId);
  const inicial = useMemo(() => (entrada ? { fecha: entrada.fecha, monto: entrada.monto } : undefined), [entrada]);
  const { fecha, setFecha, monto, setMonto } = useFechaMonto(abierto, inicial);
  const [porcentaje, setPorcentaje] = useState("");
  const [concepto, setConcepto] = useState("");
  const [referencia, setReferencia] = useState("");

  useEffect(() => {
    if (abierto) {
      setPorcentaje(entrada && Number(entrada.porcentaje_gasto) ? entrada.porcentaje_gasto : "");
      setConcepto(entrada?.concepto ?? "");
      setReferencia(entrada?.referencia ?? "");
      limpiar();
    }
  }, [abierto, entrada, limpiar]);

  const moneda = entrada?.moneda ?? destino.cuenta?.moneda;
  const calculo = calcularEntrada(monto, porcentaje);

  function guardar(e: FormEvent) {
    e.preventDefault();
    enviar(async () => {
      const datos = { fecha, monto, porcentaje_gasto: porcentaje || "0", concepto: concepto || null, referencia: referencia || null };
      if (entrada) {
        await api.patch(`/entradas/${entrada.id}`, datos);
        avisar("Entrada actualizada");
      } else {
        const { proyectoId: proyecto_id, empresaId: empresa_id, cuentaId: cuenta_id, forma } = destino.d;
        await api.post("/entradas", { ...datos, proyecto_id, empresa_id, cuenta_id, forma });
        avisar("Entrada registrada");
      }
      await invalidar();
      onCerrar();
    });
  }

  return (
    <Modal abierto={abierto} titulo={entrada ? "Editar entrada" : "Nueva entrada"} onCerrar={onCerrar} ancho="lg">
      <form onSubmit={guardar} className="space-y-4">
        {entrada ? (
          <Fijos>
            <Dato etiqueta="Proyecto">{entrada.proyecto_nombre}</Dato>
            <Dato etiqueta="Empresa">{entrada.empresa_nombre}</Dato>
            <Dato etiqueta="Cuenta">{entrada.cuenta_nombre}</Dato>
            <Dato etiqueta="Forma">{NOMBRE_FORMA[entrada.forma]} · {entrada.moneda}</Dato>
          </Fijos>
        ) : (
          destino.campos
        )}
        <div className="grid gap-4 sm:grid-cols-3">
          <Campo etiqueta="Fecha" requerido>
            {(id) => <Input id={id} type="date" required max={hoyISO()} value={fecha} onChange={(e) => setFecha(e.target.value)} />}
          </Campo>
          <Campo etiqueta={`Monto recibido${moneda ? ` (${moneda})` : ""}`} requerido>
            {(id) => <Input id={id} required inputMode="decimal" value={monto} onChange={(e) => setMonto(e.target.value)} placeholder="0.00" />}
          </Campo>
          <Campo etiqueta="% de gasto" ayuda="Opcional. Se lo queda el proveedor.">
            {(id) => <Input id={id} inputMode="decimal" value={porcentaje} onChange={(e) => setPorcentaje(e.target.value)} placeholder="0" />}
          </Campo>
        </div>
        {calculo && calculo.neto > 0 && (
          <div className="grid grid-cols-2 gap-3 rounded-md bg-neutral-50 p-3 ring-1 ring-neutral-200">
            <Dato etiqueta="Gasto del proyecto">{dinero(calculo.gasto, moneda)}</Dato>
            <Dato etiqueta="Llega a la cuenta"><strong>{dinero(calculo.neto, moneda)}</strong></Dato>
          </div>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Concepto">
            {(id) => <Input id={id} maxLength={255} value={concepto} onChange={(e) => setConcepto(e.target.value)} />}
          </Campo>
          <Campo etiqueta="Referencia" ayuda="Folio, número de transferencia, recibo…">
            {(id) => <Input id={id} maxLength={100} value={referencia} onChange={(e) => setReferencia(e.target.value)} />}
          </Campo>
        </div>
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>{entrada ? "Guardar" : "Registrar entrada"}</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}

// ------------------------------------------------------------------ salida
export function SalidaForm({ abierto, salida, proyectoId, onCerrar }: {
  abierto: boolean;
  salida?: Salida | null;
  proyectoId?: string;
  onCerrar: () => void;
}) {
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const { error, enviando, enviar, limpiar } = useEnvio();
  const destino = useDestino(abierto && !salida, proyectoId);
  const inicial = useMemo(() => (salida ? { fecha: salida.fecha, monto: salida.monto } : undefined), [salida]);
  const { fecha, setFecha, monto, setMonto } = useFechaMonto(abierto, inicial);
  const [concepto, setConcepto] = useState("");
  const [beneficiario, setBeneficiario] = useState("");

  useEffect(() => {
    if (abierto) {
      setConcepto(salida?.concepto ?? "");
      setBeneficiario(salida?.beneficiario ?? "");
      limpiar();
    }
  }, [abierto, salida, limpiar]);

  const moneda = salida?.moneda ?? destino.cuenta?.moneda;
  // El dinero de un proyecto solo puede salir de la empresa donde entró.
  const disponibleProyecto = destino.cuenta
    ? destino.proyecto?.saldos_por_empresa.find(
        (s) => s.empresa_id === destino.d.empresaId && s.moneda === destino.cuenta?.moneda,
      )?.saldo ?? "0"
    : null;

  function guardar(e: FormEvent) {
    e.preventDefault();
    enviar(async () => {
      const datos = { fecha, monto, concepto, beneficiario: beneficiario || null };
      if (salida) {
        await api.patch(`/salidas/${salida.id}`, datos);
        avisar("Salida actualizada");
      } else {
        const { proyectoId: proyecto_id, empresaId: empresa_id, cuentaId: cuenta_id, forma } = destino.d;
        await api.post("/salidas", { ...datos, proyecto_id, empresa_id, cuenta_id, forma });
        avisar("Salida registrada");
      }
      await invalidar();
      onCerrar();
    });
  }

  return (
    <Modal abierto={abierto} titulo={salida ? "Editar salida" : "Nueva salida"} onCerrar={onCerrar} ancho="lg">
      <form onSubmit={guardar} className="space-y-4">
        {salida ? (
          <Fijos>
            <Dato etiqueta="Proyecto">{salida.proyecto_nombre}</Dato>
            <Dato etiqueta="Empresa">{salida.empresa_nombre}</Dato>
            <Dato etiqueta="Cuenta">{salida.cuenta_nombre}</Dato>
            <Dato etiqueta="Forma">{NOMBRE_FORMA[salida.forma]} · {salida.moneda}</Dato>
          </Fijos>
        ) : (
          destino.campos
        )}
        {destino.cuenta && disponibleProyecto !== null && (
          <div className="grid grid-cols-2 gap-3 rounded-md bg-neutral-50 p-3 ring-1 ring-neutral-200">
            <Dato etiqueta="Disponible del proyecto en esta empresa">{dinero(disponibleProyecto, destino.cuenta.moneda)}</Dato>
            <Dato etiqueta="Saldo de la cuenta">{dinero(destino.cuenta.saldo, destino.cuenta.moneda)}</Dato>
          </div>
        )}
        {destino.cuenta && Number(disponibleProyecto) <= 0 && (
          <Aviso tono="aviso">
            {(() => {
              const otras = (destino.proyecto?.saldos_por_empresa ?? []).filter(
                (s) => s.moneda === destino.cuenta?.moneda && Number(s.saldo) > 0,
              );
              return otras.length
                ? `El proyecto no tiene ${destino.cuenta?.moneda} en esta empresa. Tiene en: ` +
                    otras.map((s) => `${s.empresa_nombre} (${dinero(s.saldo, s.moneda)})`).join(", ") + "."
                : `El proyecto no tiene ${destino.cuenta?.moneda} disponibles en ninguna empresa.`;
            })()}
          </Aviso>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Fecha" requerido>
            {(id) => <Input id={id} type="date" required max={hoyISO()} value={fecha} onChange={(e) => setFecha(e.target.value)} />}
          </Campo>
          <Campo etiqueta={`Monto${moneda ? ` (${moneda})` : ""}`} requerido>
            {(id) => <Input id={id} required inputMode="decimal" value={monto} onChange={(e) => setMonto(e.target.value)} placeholder="0.00" />}
          </Campo>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Concepto" requerido>
            {(id) => <Input id={id} required maxLength={255} value={concepto} onChange={(e) => setConcepto(e.target.value)} />}
          </Campo>
          <Campo etiqueta="Beneficiario">
            {(id) => <Input id={id} maxLength={200} value={beneficiario} onChange={(e) => setBeneficiario(e.target.value)} />}
          </Campo>
        </div>
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>{salida ? "Guardar" : "Registrar salida"}</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}
