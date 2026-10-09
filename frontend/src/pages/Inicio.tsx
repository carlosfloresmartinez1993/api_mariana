import { Link } from "react-router";
import { useAuth } from "../auth/AuthContext";
import { EncabezadoPagina, Tarjeta } from "../components/ui";
import { NOMBRE_ROL } from "../lib/types";

export default function Inicio() {
  const { usuario, esAdmin } = useAuth();
  if (!usuario) return null;
  return (
    <>
      <EncabezadoPagina titulo={`Hola, ${usuario.nombre}`} descripcion={`Entraste como ${NOMBRE_ROL[usuario.rol].toLowerCase()}.`} />
      <Tarjeta className="p-6">
        <p className="text-sm text-neutral-700">
          Pronto aquí verás los saldos por proyecto, por empresa y por cuenta.
        </p>
        {esAdmin && (
          <p className="mt-3 text-sm text-neutral-700">
            Mientras tanto puedes dar de alta a los <Link to="/usuarios" className="font-medium text-black underline">usuarios</Link> y
            revisar la <Link to="/bitacora" className="font-medium text-black underline">bitácora</Link>.
          </p>
        )}
      </Tarjeta>
    </>
  );
}
