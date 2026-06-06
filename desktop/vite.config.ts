/// <reference types="vitest" />
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
    // Card 8.5a — vitest harness, mirroring the web client. Tests run in
    // jsdom so the console's mount-time fetch + React state work the same
    // way they do in the renderer. Component tests live in src/**/*.test.tsx.
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/setupTests.ts"],
      include: ["src/**/*.test.{ts,tsx}"],
      css: false,
    },
  };
});
