/**
 * Web Surface v0.2.0 — streaming barrel (Card A22-R).
 *
 * Single import surface for the streaming controller + types.
 * Mirrors the A20-R ``forms/index.ts`` + A21-R
 * ``diagnostics/index.ts`` patterns so callers can
 * ``import { runStreamTask } from "../streaming"`` without
 * caring which file defines what.
 */

export {
  runStreamTask,
  SIMULATE_ERROR_QUERY,
} from "./controller";

export type { StreamEvent } from "./types";
