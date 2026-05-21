import type { TextStyle } from "react-native";

export const colors = {
  black: "#000000",
  deepGrey: "#111111",
  neutralGrey: "#333333",
  lightGrey: "#CCCCCC",
  darkGrey: "#888888",
  cyan: "#00F0FF",
  red: "#E02020",
  white: "#FFFFFF",
} as const;

export const spacing = {
  frame: 20,
  blockGap: 20,
  blockPadding: 12,
  buttonPaddingVertical: 16,
  gridGap: 12,
} as const;

export const typography: Record<
  "body16" | "body18" | "label12" | "label14" | "label16",
  TextStyle
> = {
  body16: { fontSize: 16, lineHeight: 24, color: colors.white },
  body18: { fontSize: 18, lineHeight: 26, color: colors.white },
  label12: { fontSize: 12, lineHeight: 16, letterSpacing: 1.2, textTransform: "uppercase" },
  label14: { fontSize: 14, lineHeight: 20, letterSpacing: 0.4 },
  label16: { fontSize: 16, lineHeight: 22, fontWeight: "500" },
};

export const geometry = {
  radius0: 0,
  radius4: 4,
} as const;

export const designSystem = { colors, spacing, typography, geometry };
