import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Pocket SPA — separate Vite project from /web. Uses port 5174 to
// avoid clashing with the cockpit dev server (5173) if both run at
// once locally.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
  },
});
