/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Dev-time proxy: forwards /api/* to your Cloud Run backend so the browser
// never deals with CORS during local development. Set VITE_API_TARGET in
// .env.local to point at your real backend, e.g.
//   VITE_API_TARGET=https://clarity-engine-xxxxx.run.app
//
// Build modes:
//   • default   → dist/        — standalone hosting (Cloud Run static)
//   • "embed"   → dist-embed/  — single app.js + app.css drop for the
//                                 WordPress plugin (integrations/wordpress-plugin/
//                                 clarityos-embed/assets/). Predictable filenames
//                                 so the plugin enqueue does not have to guess
//                                 hash suffixes.
//                                 main.tsx auto-detects #clarityos-root and
//                                 switches to HashRouter when running embedded.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_API_TARGET || "https://clarity-engine-PLACEHOLDER.run.app";
  const isEmbed = mode === "embed";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
    build: isEmbed
      ? {
          outDir: "dist-embed",
          sourcemap: false,
          // Single CSS file — the WP plugin enqueues exactly one stylesheet.
          cssCodeSplit: false,
          // Inline anything below 4KB into the JS bundle so we don't need
          // a separate /assets directory of small files in the WP plugin.
          assetsInlineLimit: 4096,
          rollupOptions: {
            output: {
              // Force a single JS chunk — no code-splitting, no vendor split.
              // Safe because /web has no React.lazy / dynamic imports.
              inlineDynamicImports: true,
              entryFileNames: "app.js",
              chunkFileNames: "app-[name].js",
              assetFileNames: (info) => {
                if (info.name && info.name.endsWith(".css")) return "app.css";
                return "assets/[name][extname]";
              },
            },
          },
        }
      : {
          outDir: "dist",
          sourcemap: true,
        },
    // v48 — vitest config. Tests run in a jsdom environment so the
    // routes that touch ``window`` / ``localStorage`` work the same
    // way they do in the browser.
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test-setup.ts"],
      include: ["src/**/*.test.{ts,tsx}"],
      css: false,
    },
  };
});
