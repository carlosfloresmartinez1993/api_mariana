import { useEffect, useState, type FormEvent } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { Icono } from "../components/Icono";
import { useToast } from "../components/Toast";
import {
  Boton,
  Campo,
  Cargando,
  EncabezadoPagina,
  ErrorApi,
  Input,
  Insignia,
  Modal,
  Paginacion,
  PieModal,
  Select,
  Tabla,
  Tarjeta,
  Td,
  Th,
  Vacio,
} from "../components/ui";
import { api } from "../lib/api";
import { fecha } from "../lib/format";
import { useFiltros } from "../lib/filtros";
import { NOMBRE_ROL, type Pagina, type Rol, type Usuario } from "../lib/types";

const LIMITE = 50;
const CLAVES = ["rol", "activo"] as const;
const AYUDA_PASSWORD = "Mínimo 8 caracteres, con letras y números.";

type RolAsignable = Exclude<Rol, "superusuario">;

/** El superusuario administra admins y contadores; un admin, solo contadores. */
function useRolesAdministrables(): RolAsignable[] {
  const { esSuperusuario } = useAuth();
  return esSuperusuario ? ["admin", "contador"] : ["contador"];
}

function useRefrescarUsuarios() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ["usuarios"] });
}

function UsuarioForm({ abierto, usuario, onCerrar }: { abierto: boolean; usuario: Usuario | null; onCerrar: () => void }) {
  const avisar = useToast();
  const refrescar = useRefrescarUsuarios();
  const roles = useRolesAdministrables();
  const [nombre, setNombre] = useState("");
  const [correo, setCorreo] = useState("");
  const [rol, setRol] = useState<RolAsignable>("contador");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (abierto) {
      setNombre(usuario?.nombre ?? "");
      setCorreo(usuario?.correo ?? "");
      setRol(usuario && usuario.rol !== "superusuario" ? usuario.rol : "contador");
      setPassword("");
      setError(null);
    }
  }, [abierto, usuario]);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    const datos = { nombre: nombre.trim(), correo: correo.trim(), ...(roles.length > 1 ? { rol } : {}) };
    try {
      if (usuario) {
        await api.patch(`/usuarios/${usuario.id}`, datos);
        avisar("Usuario actualizado");
      } else {
        await api.post("/usuarios", { ...datos, rol, password });
        avisar("Usuario creado");
      }
      refrescar();
      onCerrar();
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal abierto={abierto} titulo={usuario ? "Editar usuario" : "Nuevo usuario"} onCerrar={onCerrar}>
      <form onSubmit={guardar} className="space-y-4">
        <Campo etiqueta="Nombre" requerido>
          {(id) => <Input id={id} required maxLength={150} value={nombre} onChange={(e) => setNombre(e.target.value)} />}
        </Campo>
        <Campo etiqueta="Correo" requerido>
          {(id) => <Input id={id} type="email" required value={correo} onChange={(e) => setCorreo(e.target.value)} />}
        </Campo>
        {roles.length > 1 ? (
          <Campo etiqueta="Rol" requerido ayuda="El administrador ve y corrige todo, y da de alta a los contadores.">
            {(id) => (
              <Select id={id} value={rol} onChange={(e) => setRol(e.target.value as RolAsignable)}>
                {roles.map((r) => <option key={r} value={r}>{NOMBRE_ROL[r]}</option>)}
              </Select>
            )}
          </Campo>
        ) : (
          !usuario && <p className="text-sm text-neutral-600">Se creará como <strong>contador</strong>.</p>
        )}
        {!usuario && (
          <Campo etiqueta="Contraseña inicial" requerido ayuda={AYUDA_PASSWORD}>
            {(id) => <Input id={id} type="password" autoComplete="new-password" required minLength={8} maxLength={72}
              value={password} onChange={(e) => setPassword(e.target.value)} />}
          </Campo>
        )}
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>{usuario ? "Guardar cambios" : "Crear usuario"}</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}

function RestablecerPassword({ usuario, onCerrar }: { usuario: Usuario | null; onCerrar: () => void }) {
  const avisar = useToast();
  const [nueva, setNueva] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    setNueva("");
    setError(null);
  }, [usuario]);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    if (!usuario) return;
    setEnviando(true);
    setError(null);
    try {
      await api.post(`/usuarios/${usuario.id}/restablecer-password`, { nueva });
      avisar("Contraseña restablecida");
      onCerrar();
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal abierto={usuario !== null} titulo="Restablecer contraseña"
      descripcion={usuario ? `${usuario.nombre} · ${usuario.correo}` : undefined} onCerrar={onCerrar}>
      <form onSubmit={guardar} className="space-y-4">
        <Campo etiqueta="Nueva contraseña" requerido ayuda={AYUDA_PASSWORD}>
          {(id) => <Input id={id} type="password" autoComplete="new-password" required minLength={8} maxLength={72}
            value={nueva} onChange={(e) => setNueva(e.target.value)} />}
        </Campo>
        <ErrorApi error={error} />
        <PieModal>
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>Restablecer</Boton>
        </PieModal>
      </form>
    </Modal>
  );
}

export default function Usuarios() {
  const { usuario: yo } = useAuth();
  const avisar = useToast();
  const refrescar = useRefrescarUsuarios();
  const administrables = useRolesAdministrables();
  const { filtros, offset, cambiar } = useFiltros(CLAVES);
  const [formAbierto, setFormAbierto] = useState(false);
  const [editando, setEditando] = useState<Usuario | null>(null);
  const [restableciendo, setRestableciendo] = useState<Usuario | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["usuarios", "lista", filtros, offset],
    queryFn: () => api.get<Pagina<Usuario>>("/usuarios", { ...filtros, limit: LIMITE, offset }),
    placeholderData: keepPreviousData,
  });

  const puedeAdministrar = (u: Usuario) => u.rol !== "superusuario" && administrables.includes(u.rol);

  async function alternar(u: Usuario) {
    if (u.activo && !confirm(`¿Desactivar a ${u.nombre}? Perderá el acceso de inmediato.`)) return;
    try {
      await api.post(`/usuarios/${u.id}/${u.activo ? "desactivar" : "activar"}`);
      avisar(u.activo ? "Usuario desactivado" : "Usuario activado");
      refrescar();
    } catch (e) {
      avisar((e as Error).message, "error");
    }
  }

  return (
    <>
      <EncabezadoPagina
        titulo="Usuarios"
        descripcion="Quién tiene acceso al sistema y con qué rol."
        acciones={
          <Boton onClick={() => { setEditando(null); setFormAbierto(true); }}>
            <Icono nombre="mas" className="size-4" /> Nuevo usuario
          </Boton>
        }
      />

      <Tarjeta className="mb-4 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Campo etiqueta="Rol">
            {(id) => (
              <Select id={id} value={filtros.rol} onChange={(e) => cambiar({ rol: e.target.value })}>
                <option value="">Todos</option>
                <option value="superusuario">Superusuario</option>
                <option value="admin">Administradores</option>
                <option value="contador">Contadores</option>
              </Select>
            )}
          </Campo>
          <Campo etiqueta="Estado">
            {(id) => (
              <Select id={id} value={filtros.activo} onChange={(e) => cambiar({ activo: e.target.value })}>
                <option value="">Todos</option>
                <option value="true">Activos</option>
                <option value="false">Inactivos</option>
              </Select>
            )}
          </Campo>
        </div>
      </Tarjeta>

      <ErrorApi error={error} className="mb-4" />

      <Tarjeta>
        {isLoading ? (
          <Cargando />
        ) : !data?.items.length ? (
          <Vacio titulo="No hay usuarios con esos filtros" />
        ) : (
          <>
            <Tabla>
              <thead>
                <tr>
                  <Th>Usuario</Th>
                  <Th>Rol</Th>
                  <Th>Estado</Th>
                  <Th>Alta</Th>
                  <Th><span className="sr-only">Acciones</span></Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {data.items.map((u) => (
                  <tr key={u.id} className="hover:bg-neutral-50">
                    <Td>
                      <p className="font-medium text-black">
                        {u.nombre} {u.id === yo?.id && <span className="text-xs font-normal text-neutral-500">(tú)</span>}
                      </p>
                      <p className="text-xs text-neutral-500">{u.correo}</p>
                    </Td>
                    <Td><Insignia tono={u.rol === "contador" ? "neutro" : "fuerte"}>{NOMBRE_ROL[u.rol]}</Insignia></Td>
                    <Td>{u.activo ? <Insignia>Activo</Insignia> : <Insignia tono="tenue">Inactivo</Insignia>}</Td>
                    <Td className="whitespace-nowrap">{fecha(u.fecha_creacion)}</Td>
                    <Td className="whitespace-nowrap text-right">
                      {puedeAdministrar(u) && (
                        <>
                          <Boton variante="fantasma" tamano="sm" onClick={() => { setEditando(u); setFormAbierto(true); }}>Editar</Boton>
                          <Boton variante="fantasma" tamano="sm" onClick={() => setRestableciendo(u)}>Contraseña</Boton>
                          <Boton variante="fantasma" tamano="sm" onClick={() => alternar(u)}>
                            {u.activo ? "Desactivar" : "Activar"}
                          </Boton>
                        </>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Tabla>
            <Paginacion total={data.total} limit={LIMITE} offset={offset} onCambiar={(o) => cambiar({ offset: o })} />
          </>
        )}
      </Tarjeta>

      <UsuarioForm abierto={formAbierto} usuario={editando} onCerrar={() => setFormAbierto(false)} />
      <RestablecerPassword usuario={restableciendo} onCerrar={() => setRestableciendo(null)} />
    </>
  );
}
