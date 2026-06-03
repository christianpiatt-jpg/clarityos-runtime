import { defineConfig } from "vitest/config";
// Node-env runner for the pure operator-lib scaffolds (no React Native runtime).
export default defineConfig({ test: { environment: "node", include: ["lib/__tests__/**/*.test.ts"] } });
