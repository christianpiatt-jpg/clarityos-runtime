import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Surface v1 harness. Strict-port + loopback host so the dev server
// is predictable across runs.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    host: "127.0.0.1",
  },
});
