import { useCallback, useState } from "react";

/** Estado de envío de un formulario: `enviar(fn)` ejecuta la petición y guarda el error si falla. */
export function useEnvio() {
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  const enviar = useCallback(async (fn: () => Promise<void>) => {
    setEnviando(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }, []);

  const limpiar = useCallback(() => setError(null), []);

  return { error, enviando, enviar, limpiar, setError };
}
