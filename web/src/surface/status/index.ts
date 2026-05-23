/**
 * Web Surface v0.2.0 — status barrel (Card A23-R).
 *
 * Single import surface for the status renderer + types.
 * Mirrors the A20-R ``forms/index.ts``, A21-R
 * ``diagnostics/index.ts``, and A22-R ``streaming/index.ts``
 * patterns so callers can
 * ``import { renderStatusSurface } from "../status"`` without
 * caring which file defines what.
 */

export {
  renderStatusSurface,
  STATUS_TEMPLATE_NAMES,
  escapeHtml,
} from "./render";

export type {
  StatusKind,
  StatusPayload,
} from "./types";
