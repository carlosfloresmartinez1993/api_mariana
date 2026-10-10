import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { api } from "../../lib/api";
import { useInvalidarDinero } from "../../lib/queries";
import { useEnvio } from "../../lib/useEnvio";
import { useToast } from "../Toast";
import { Boton, Campo, ErrorApi, Modal, PieModal, Textarea } from "../ui";

/** Pide el motivo y anula un movimiento (POST {ruta}/anular). No se borra: deja de contar en los saldos. */
export function Anular({ ruta, titulo, resumen, onCerrar }: {
  ruta: string | null;
  titulo: string;
  resumen?: ReactNode;
  onCerrar: () => void;
}) {
  const avisar = useToast();
  const invalidar = useInvalidarDinero();
  const { error, enviando, enviar, limpiar } = useEnvio();
  const [motivo, setMotivo] = useState("");

  useEffect(() => {
    setMotivo("");
    limpiar();
  }, [ruta, limpiar]);

  function guardar(e: FormEvent) {
    e.preventDefault();
    if (!ruta) return;
    enviar(async () => {
      await api.post(`${ruta}/anular`, { motivo: motivo.trim() });
      await invalidar();
      avisar("Movimiento anulado");
      onCerrar();
    });
  }

  return (
    <Modal abierto={ruta !== null} titulo={titulo} onCerrar={onCerrar}
      descripcion="El movimiento no se borra: queda anulado, deja de contar en los saldos y se registra en la bitácora.">
      <form onSubmit={guardar} className="space-y-4">
        {resumen && <div className="rounded-md bg-neutral-50 p-3 text-sm ring-1 ring-neutral-200">{resumen}</div>}
        <Campo etiqueta="Motivo" requerido>
          {(id) => <Textarea id={id} required minLength={3} maxLength={500} value={motivo}
            onChange={(e) => setMotivo(e.target.value)} placeholder="Por qué se anula" />}
        </Campo>
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" variante="peligro" cargando={enviando}>Anular</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}
