import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// En desarrollo, /api se redirige al backend de FastAPI; así no hay problemas de CORS
// y el navegador puede leer las cabeceras de las descargas.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backend = env.BACKEND_URL || "http://localhost:8000";
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      proxy: {
        "/api": { target: backend, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") },
      },
    },
  };
});
