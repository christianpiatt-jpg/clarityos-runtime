/**
 * Web Surface v0.2.0 — diagnostics barrel (Card A21-R).
 *
 * Single import surface for the diagnostic collector + types.
 * Mirrors the A20-R ``forms/index.ts`` pattern so callers can
 * ``import { collectDiagnostics } from "../diagnostics"`` without
 * caring which file defines what.
 */

export { collectDiagnostics } from "./collect";

export type {
  DiagnosticEntry,
  DiagnosticPayload,
} from "./types";
