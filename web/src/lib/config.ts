// Single source of truth for the backend URL.
// Resolution order (last non-empty wins, from most to least specific):
//   1. localStorage `clarityos_api_base`               (per-browser override)
//   2. window.CLARITYOS_API_BASE                       (host-page injected — WP embed)
//   3. VITE_API_BASE env var                           (build-time)
//   4. The DEFAULT below
//
// In dev (vite), prefer setting VITE_API_TARGET to your Cloud Run URL —
// vite.config.ts proxies /api/* there, and you can leave API_BASE = "/api"
// to avoid CORS entirely.
//
// The window-level slot exists so the WordPress plugin can inject the
// backend URL inline before app.js runs, without rebuilding the bundle
// per WP install. The plugin emits:
//   <script>window.CLARITYOS_API_BASE = "https://...";</script>

declare global {
  interface Window {
    CLARITYOS_API_BASE?: string;
  }
}

const DEFAULT_API_BASE = "https://clarity-engine-736968277491.us-central1.run.app";

function resolveBase(): string {
  try {
    const stored = localStorage.getItem("clarityos_api_base");
    if (stored) return stored.replace(/\/+$/, "");
  } catch { /* SSR / disabled storage */ }
  if (typeof window !== "undefined" && window.CLARITYOS_API_BASE) {
    return window.CLARITYOS_API_BASE.replace(/\/+$/, "");
  }
  const env = import.meta.env.VITE_API_BASE;
  return (env || DEFAULT_API_BASE).replace(/\/+$/, "");
}

export const APP_CONFIG = {
  API_BASE: resolveBase(),
  IS_PLACEHOLDER: resolveBase().includes("PLACEHOLDER"),
  VERSION: "0.2.0",
} as const;

export function getApiBase(): string {
  return APP_CONFIG.API_BASE;
}

export function setApiBaseOverride(url: string | null): void {
  try {
    if (url) localStorage.setItem("clarityos_api_base", url);
    else localStorage.removeItem("clarityos_api_base");
    // Force a reload so APP_CONFIG re-resolves.
    location.reload();
  } catch { /* noop */ }
}
