/**
 * Web Surface v0.2.0 — loading barrel (Card A24-R).
 *
 * Single import surface for the loading renderer + types.
 * Mirrors the A20-R ``forms/index.ts``, A21-R
 * ``diagnostics/index.ts``, A22-R ``streaming/index.ts``, and
 * A23-R ``status/index.ts`` patterns so callers can
 * ``import { renderLoadingSurface } from "../loading"`` without
 * caring which file defines what.
 */

export {
  renderLoadingSurface,
  DEFAULT_LOADING_MESSAGE,
  LOADING_TEMPLATE_NAME,
  escapeHtml,
} from "./render";

export type { LoadingPayload } from "./types";
