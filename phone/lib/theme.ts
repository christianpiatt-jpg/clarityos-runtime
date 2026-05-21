// Mirrors web/assets/css/clarityos.css :root tokens. If you change one,
// change both. Web and phone share these values verbatim so the orb,
// surfaces, and accents are identical across surfaces.

export const colors = {
  bgDeep: "#050810",
  bgSurface: "#0c1220",
  bgElevated: "#131a2c",
  border: "#1f2940",
  borderStrong: "#2a3550",
  textPrimary: "#e8ecf5",
  textSecondary: "#8893a8",
  textTertiary: "#5a6477",
  accent: "#6ee7ff",
  accentDeep: "#2563eb",
  accentViolet: "#8b5cf6",
  success: "#4ade80",
  warning: "#fbbf24",
  danger: "#f87171",
} as const;

export const fonts = {
  sans: "System",
  mono: "Menlo",
} as const;

export const radius = {
  sm: 6,
  md: 12,
  lg: 20,
  pill: 999,
} as const;

export const space = {
  s1: 4,
  s2: 8,
  s3: 12,
  s4: 16,
  s5: 24,
  s6: 32,
  s7: 48,
  s8: 64,
} as const;

export const theme = { colors, fonts, radius, space };
export type Theme = typeof theme;
