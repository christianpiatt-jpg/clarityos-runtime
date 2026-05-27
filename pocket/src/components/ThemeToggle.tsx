import { useTheme } from "../lib/theme";

/**
 * ThemeToggle — manual override between light and dark. Persists
 * the choice in localStorage so subsequent loads skip the system
 * preference. (Reset to "follow system" by clearing
 * ``clarityos_pocket_theme`` in DevTools — there is intentionally
 * no UI for that yet.)
 */
export default function ThemeToggle() {
  const [theme, setTheme] = useTheme();
  const next = theme === "dark" ? "light" : "dark";
  return (
    <button
      type="button"
      className="pkt-theme-toggle"
      onClick={() => setTheme(next)}
      aria-label={`Switch to ${next} mode`}
      title={`Switch to ${next} mode`}
    >
      {theme === "dark" ? (
        // sun glyph — appears in dark mode (click to go light)
        <span aria-hidden="true">&#9728;</span>
      ) : (
        // crescent moon — appears in light mode (click to go dark)
        <span aria-hidden="true">&#9790;</span>
      )}
    </button>
  );
}
