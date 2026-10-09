import { useState, type FormEvent } from "react";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { Aviso, Boton, Campo, EncabezadoPagina, ErrorApi, Input, Tarjeta } from "../components/ui";
import { api } from "../lib/api";

export default function Perfil() {
  const { usuario } = useAuth();
  const avisar = useToast();
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    if (nueva !== confirmacion) {
      setError(new Error("La confirmación no coincide con la nueva contraseña"));
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      await api.post("/auth/cambiar-password", { actual, nueva });
      avisar("Contraseña actualizada");
      setActual("");
      setNueva("");
      setConfirmacion("");
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <>
      <EncabezadoPagina titulo="Cambiar contraseña" descripcion={usuario?.correo} />
      <Tarjeta className="max-w-lg p-6">
        <form onSubmit={guardar} className="space-y-4">
          <Campo etiqueta="Contraseña actual" requerido>
            {(id) => <Input id={id} type="password" autoComplete="current-password" required value={actual} onChange={(e) => setActual(e.target.value)} />}
          </Campo>
          <Campo etiqueta="Nueva contraseña" requerido ayuda="Mínimo 8 caracteres, con letras y números.">
            {(id) => <Input id={id} type="password" autoComplete="new-password" required minLength={8} maxLength={72}
              value={nueva} onChange={(e) => setNueva(e.target.value)} />}
          </Campo>
          <Campo etiqueta="Confirmar nueva contraseña" requerido>
            {(id) => <Input id={id} type="password" autoComplete="new-password" required value={confirmacion} onChange={(e) => setConfirmacion(e.target.value)} />}
          </Campo>
          {confirmacion && nueva !== confirmacion && <Aviso tono="aviso">Las contraseñas no coinciden.</Aviso>}
          <ErrorApi error={error} />
          <div className="flex justify-end">
            <Boton type="submit" cargando={enviando}>Actualizar contraseña</Boton>
          </div>
        </form>
      </Tarjeta>
    </>
  );
}
