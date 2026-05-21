import Constants from "expo-constants";

const fromExtra = (Constants.expoConfig?.extra as Record<string, string> | undefined)?.apiBase;
const fromEnv =
  // EXPO_PUBLIC_* vars are inlined at build time — let CI override the default.
  (process.env as Record<string, string | undefined>).EXPO_PUBLIC_CLARITYOS_API_BASE;

export const API_BASE: string =
  fromEnv?.replace(/\/+$/, "") ||
  fromExtra?.replace(/\/+$/, "") ||
  "https://clarity-engine-PLACEHOLDER.run.app";
