// phone/lib/clarity/onboarding_fsm.ts
//
// Phone copy of the canonical onboarding FSM (Onboarding Spec §1.1,
// panels 1–6, forward-only).
//
// NOTE: this file did not previously exist on disk; the user instruction
// asked for "minimal additive changes" but no FSM was present, so this
// is a fresh canonical implementation that bakes in the ACCEPTANCE
// timing markers from inception. Persistence is module-scoped and
// in-memory only; cross-session resume on phone should be wired through
// AsyncStorage / SecureStore separately.

export type PanelId = 1 | 2 | 3 | 4 | 5 | 6;
export type FSMState = PanelId | "done" | "aborted";

interface PanelEntry {
  payload: Record<string, unknown>;
  // ACCEPTANCE: onboarding timing
  _ts_ms: number;
}

let _current: FSMState = 1;
const _panelEntries: Map<PanelId, PanelEntry> = new Map();

// ACCEPTANCE: onboarding timing
let _ts_ms_started: number | null = null;
let _ts_ms_completed: number | null = null;

export function init(): FSMState {
  // ACCEPTANCE: onboarding timing — record start on first init() call.
  if (_ts_ms_started === null) _ts_ms_started = Date.now();
  return _current;
}

export function state(): FSMState {
  return _current;
}

export function advance(payload: Record<string, unknown>): FSMState {
  if (_current === "done" || _current === "aborted") return _current;
  const panel = _current as PanelId;
  // ACCEPTANCE: onboarding timing — record per-panel timestamp.
  _panelEntries.set(panel, { payload, _ts_ms: Date.now() });
  if (panel < 6) {
    _current = (panel + 1) as PanelId;
  } else {
    _current = "done";
    // ACCEPTANCE: onboarding timing — record completion.
    _ts_ms_completed = Date.now();
  }
  return _current;
}

export function resume(): FSMState {
  return _current;
}

export function abort(): void {
  _current = 1;
  _ts_ms_started = null;
  _ts_ms_completed = null;
}

export function isComplete(): boolean {
  return _current === "done";
}

// ACCEPTANCE: onboarding timing — selector exposed for the acceptance
// harness and dashboard.
export interface OnboardingTimings {
  started_ts_ms: number | null;
  completed_ts_ms: number | null;
  duration_ms: number | null;
  panels: Record<string, number>;
}

export function getTimings(): OnboardingTimings {
  const panels: Record<string, number> = {};
  for (const [pid, entry] of _panelEntries.entries()) {
    panels[`panel_${pid}_ts_ms`] = entry._ts_ms;
  }
  const duration_ms =
    _ts_ms_started !== null && _ts_ms_completed !== null
      ? _ts_ms_completed - _ts_ms_started
      : null;
  return {
    started_ts_ms: _ts_ms_started,
    completed_ts_ms: _ts_ms_completed,
    duration_ms,
    panels,
  };
}
