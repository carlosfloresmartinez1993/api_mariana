import { useEffect, useState, type FormEvent } from "react";
import { api } from "../../lib/api";
import { useInvalidarDinero } from "../../lib/queries";
import { MONEDAS, type Cuenta, type Moneda, type TipoCuenta } from "../../lib/types";
import { useEnvio } from "../../lib/useEnvio";
import { useToast } from "../Toast";
import { Boton, Campo, ErrorApi, Input, Modal, Opciones, PieModal } from "../ui";

/** Alta (con tipo y moneda) o edición (solo nombre, banco y número) de una cuenta. */
export function CuentaForm({ abierto, empresaId, cuenta, onCerrar }: {
  abierto: boolean;
  empresaId: string;
  cuenta?: Cuenta | null;
  onCerrar: () => void;
}) {
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const { error, enviando, enviar, limpiar } = useEnvio();
  const [tipo, setTipo] = useState<TipoCuenta>("banco");
  const [moneda, setMoneda] = useState<Moneda>("MXN");
  const [nombre, setNombre] = useState("");
  const [banco, setBanco] = useState("");
  const [numero, setNumero] = useState("");

  useEffect(() => {
    if (abierto) {
      setTipo(cuenta?.tipo ?? "banco");
      setMoneda(cuenta?.moneda ?? "MXN");
      setNombre(cuenta?.nombre ?? "");
      setBanco(cuenta?.banco ?? "");
      setNumero(cuenta?.numero ?? "");
      limpiar();
    }
  }, [abierto, cuenta, limpiar]);

  function guardar(e: FormEvent) {
    e.preventDefault();
    enviar(async () => {
      const textos = {
        nombre: nombre.trim() || null,
        banco: tipo === "banco" ? banco.trim() || null : null,
        numero: tipo === "banco" ? numero.trim() || null : null,
      };
      if (cuenta) {
        await api.patch(`/cuentas/${cuenta.id}`, { ...textos, nombre: textos.nombre ?? cuenta.nombre });
        avisar("Cuenta actualizada");
      } else {
        await api.post("/cuentas", { empresa_id: empresaId, tipo, moneda, ...textos });
        avisar(tipo === "caja" ? "Caja creada" : "Cuenta creada");
      }
      await invalidar();
      onCerrar();
    });
  }

  const nombrePorDefecto = tipo === "caja" ? `Caja ${moneda}` : `${banco.trim() || "Banco"} ${moneda}`;

  return (
    <Modal abierto={abierto} titulo={cuenta ? "Editar cuenta" : "Nueva cuenta"} onCerrar={onCerrar}>
      <form onSubmit={guardar} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Tipo">
            {() => <Opciones valor={tipo} onCambiar={setTipo} deshabilitado={!!cuenta}
              opciones={[{ valor: "banco", texto: "Banco" }, { valor: "caja", texto: "Caja (efectivo)" }]} />}
          </Campo>
          <Campo etiqueta="Moneda" ayuda={cuenta ? "La moneda no se puede cambiar." : "Después ya no se podrá cambiar."}>
            {() => <Opciones valor={moneda} onCambiar={setMoneda} deshabilitado={!!cuenta}
              opciones={MONEDAS.map((m) => ({ valor: m, texto: m }))} />}
          </Campo>
        </div>
        {tipo === "banco" && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Campo etiqueta="Banco">
              {(id) => <Input id={id} maxLength={100} value={banco} onChange={(e) => setBanco(e.target.value)} placeholder="BBVA" />}
            </Campo>
            <Campo etiqueta="Número de cuenta o CLABE">
              {(id) => <Input id={id} maxLength={30} value={numero} onChange={(e) => setNumero(e.target.value)} />}
            </Campo>
          </div>
        )}
        <Campo etiqueta="Nombre" ayuda={cuenta ? undefined : `Si lo dejas vacío: «${nombrePorDefecto}».`}>
          {(id) => <Input id={id} maxLength={100} value={nombre} onChange={(e) => setNombre(e.target.value)}
            placeholder={nombrePorDefecto} required={!!cuenta} />}
        </Campo>
        {!cuenta && (
          <p className="text-xs text-neutral-500">
            La cuenta empieza en cero. Si ya tenía dinero, regístralo como una entrada del proyecto al que pertenece
            (por ejemplo, con el concepto «Saldo de apertura»).
          </p>
        )}
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>{cuenta ? "Guardar" : "Crear"}</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}
