/**
 * Pocket — theme helpers.
 *
 * Light/dark mode is driven by CSS custom properties on
 * ``<html>``. There are three "states" a viewer can be in:
 *
 *   * ``light``  — explicit user choice, persisted in localStorage
 *   * ``dark``   — explicit user choice, persisted in localStorage
 *   * (no stored value) — follow ``prefers-color-scheme``
 *
 * To prevent a flash of the wrong palette before React mounts, a
 * small bootstrap script in ``index.html`` reads
 * ``localStorage.clarityos_pocket_theme`` and sets the
 * ``data-theme`` attribute on ``<html>`` BEFORE the CSS bundle
 * loads. This module is what React uses after mount to read +
 * mutate that state.
 */
import { useEffect, useState } from "react";

export type Theme = "light" | "dark";

const THEME_KEY = "clarityos_pocket_theme";

export function getStoredTheme(): Theme | null {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

export function setStoredTheme(t: Theme | null): void {
  try {
    if (t) localStorage.setItem(THEME_KEY, t);
    else localStorage.removeItem(THEME_KEY);
  } catch {
    /* localStorage disabled */
  }
}

export function getSystemTheme(): Theme {
  if (typeof window === "undefined" || !window.matchMedia) return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

/** Effective theme = stored choice, falling back to system. */
export function getEffectiveTheme(): Theme {
  return getStoredTheme() ?? getSystemTheme();
}

/** Write ``data-theme`` on <html> (or remove for "follow system"). */
export function applyTheme(t: Theme | null): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (t) root.setAttribute("data-theme", t);
  else root.removeAttribute("data-theme");
}

/**
 * React hook: returns ``[effective, setTheme]``. ``setTheme(null)``
 * clears the stored choice and reverts to system preference.
 */
export function useTheme(): [Theme, (t: Theme | null) => void] {
  const [theme, setThemeState] = useState<Theme>(() => getEffectiveTheme());

  useEffect(() => {
    // Re-sync if the system preference changes mid-session AND the
    // user hasn't explicitly chosen a mode.
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      if (getStoredTheme() === null) setThemeState(getSystemTheme());
    };
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);

  function setTheme(t: Theme | null) {
    setStoredTheme(t);
    applyTheme(t);
    setThemeState(t ?? getSystemTheme());
  }

  return [theme, setTheme];
}
