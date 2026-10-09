import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";
import { useAuth } from "../auth/AuthContext";
import { Aviso, Boton, Campo, Input } from "../components/ui";

export default function Login() {
  const { usuario, entrar, aviso } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const destino = (location.state as { desde?: string } | null)?.desde ?? "/";

  const [correo, setCorreo] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  if (usuario) return <Navigate to={destino} replace />;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      await entrar(correo.trim(), password);
      navigate(destino, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesión");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="flex min-h-dvh">
      <div className="hidden flex-1 flex-col justify-between bg-black p-12 text-white lg:flex">
        <div className="flex items-center gap-3">
          <img src="/favicon.svg" alt="" className="size-10" />
          <span className="text-lg font-semibold">Control de Empresas y Proyectos</span>
        </div>
        <div className="max-w-md">
          <h2 className="text-3xl font-semibold leading-tight">Entradas, salidas y saldos de cada proyecto.</h2>
          <p className="mt-4 text-neutral-400">
            Controla el dinero por empresa, cuenta de banco y caja, en pesos y en dólares.
          </p>
        </div>
        <p className="text-sm text-neutral-500">Cada operación queda registrada en la bitácora.</p>
      </div>

      <div className="flex flex-1 items-center justify-center px-4 py-12 sm:px-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <img src="/favicon.svg" alt="" className="size-10" />
            <span className="text-lg font-semibold text-black">Control de Empresas y Proyectos</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-black">Iniciar sesión</h1>
          <p className="mt-1 text-sm text-neutral-500">Usa el correo y la contraseña que te dio el administrador.</p>

          <form onSubmit={enviar} className="mt-8 space-y-5">
            {aviso && !error && <Aviso tono="aviso">{aviso}</Aviso>}
            {error && <Aviso tono="peligro">{error}</Aviso>}
            <Campo etiqueta="Correo electrónico">
              {(id) => (
                <Input id={id} type="email" autoComplete="email" required autoFocus value={correo}
                  onChange={(e) => setCorreo(e.target.value)} />
              )}
            </Campo>
            <Campo etiqueta="Contraseña">
              {(id) => (
                <Input id={id} type="password" autoComplete="current-password" required value={password}
                  onChange={(e) => setPassword(e.target.value)} />
              )}
            </Campo>
            <Boton type="submit" cargando={enviando} className="w-full">
              Entrar
            </Boton>
          </form>
        </div>
      </div>
    </div>
  );
}
