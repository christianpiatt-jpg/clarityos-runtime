// tests/acceptance/timer.ts
//
// Tiny timing helper used by scenarios to measure onboarding and
// surface-jump windows.

export interface RunningTimer {
  label: string;
  start_ms: number;
  stop: () => number;          // returns elapsed ms
  elapsed: () => number;       // returns elapsed ms without stopping
}

export function startTimer(label: string): RunningTimer {
  const start_ms = Date.now();
  let stopped: number | null = null;
  return {
    label,
    start_ms,
    stop: () => {
      if (stopped === null) stopped = Date.now() - start_ms;
      return stopped;
    },
    elapsed: () => stopped ?? Date.now() - start_ms,
  };
}
