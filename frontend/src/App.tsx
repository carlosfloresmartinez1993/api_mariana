import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router";
import { useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { Cargando } from "./components/ui";
import Login from "./pages/Login";
import Inicio from "./pages/Inicio";
import Usuarios from "./pages/Usuarios";
import Bitacora from "./pages/Bitacora";
import Perfil from "./pages/Perfil";

function Protegida({ children, soloAdmin = false }: { children: ReactNode; soloAdmin?: boolean }) {
  const { usuario, cargando, esAdmin } = useAuth();
  const location = useLocation();
  if (cargando) return <div className="min-h-dvh"><Cargando texto="Verificando sesión…" /></div>;
  if (!usuario) return <Navigate to="/login" replace state={{ desde: location.pathname }} />;
  if (soloAdmin && !esAdmin) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <Protegida>
            <Layout />
          </Protegida>
        }
      >
        <Route index element={<Inicio />} />
        <Route path="usuarios" element={<Protegida soloAdmin><Usuarios /></Protegida>} />
        <Route path="bitacora" element={<Protegida soloAdmin><Bitacora /></Protegida>} />
        <Route path="perfil" element={<Perfil />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
