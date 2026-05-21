import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Vite config for the desktop renderer process. The Electron main
// process loads the dist/ build in production and the dev server in
// development. Port 5174 (one above the web client's 5173) so both
// can run in parallel without colliding.
//
// VITE_API_BASE — backend URL the renderer talks to. Defaults to
// production Cloud Run; override per-machine via .env.local.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    base: "./",   // load assets via relative paths so file:// works
    server: {
      port: 5174,
      strictPort: true,
    },
    define: {
      // Surface the configured backend URL into the renderer at build time.
      "import.meta.env.VITE_API_BASE": JSON.stringify(
        env.VITE_API_BASE || "https://clarity-engine-PLACEHOLDER.run.app",
      ),
    },
    build: {
      outDir: "dist",
      sourcemap: true,
      emptyOutDir: true,
    },
  };
});
