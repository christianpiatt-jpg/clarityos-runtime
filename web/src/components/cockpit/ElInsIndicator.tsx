// v69 / Unit 74 — Cockpit EL/INS indicator.
//
// Compact stability badge that reads the most recent EL/INS record
// for the authed operator and displays a one-glance classification
// label with a tap-through to the full /operator/el_ins surface.
//
// Behaviour:
//   - Reads ONE route on mount, /el_ins/operator/reasoning_mode (#290: the
//     operator's default scope; the cockpit's selected thread is passed so
//     that thread's on-demand analyses count while it is selected).
//   - Renders a small card with: "Stability: Balanced" / "High-EL" /
//     "High-INS", plus a tooltip with the latest stability_notes when
//     present.
//   - Empty state ("never analyzed") shows a muted "—" badge and
//     still links to the dashboard.
//   - Errors don't break the cockpit layout — the indicator silently
//     hides itself.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useCockpit } from "../../state/cockpitStore";
import {
  getElInsAnomalies,
  getElInsReasoningMode,
  getTimeline,
  type ElInsReasoningModeLabel,
  type ElInsReasoningModeResponse,
} from "../../lib/api";
import { elInsClassColor } from "../../lib/labels";

// v72 / Unit 80 — anomaly "new" window. The red dot fires when at
// least one anomaly was emitted in the last 24h. No client-side
// last-seen state — keeps the badge simple and stateless across
// devices.
const ANOMALY_NEW_WINDOW_SECONDS = 60 * 60 * 24;

// v73 / Unit 82 — timeline "new" window. Parallel to the anomaly
// badge: dot fires when at least one timeline event landed in the
// last 24h. Same statelessness.
const TIMELINE_NEW_WINDOW_SECONDS = 60 * 60 * 24;

const LABELS: Record<string, string> = {
  balanced: "Balanced",
  high_el:  "High-EL",
  high_ins: "High-INS",
  // #374 -- a 0/0 read has no position to name. An em dash, the same way
  // every other absent value reads on this badge; the raw key still rides
  // in the title attribute beside the EL/INS numbers.
  UNMAPPED: "—",
};

// v71 / Unit 79 — Display labels for reasoning_mode. Locked here so
// the strings can be updated without touching the kernel.
const MODE_LABELS: Record<string, string> = {
  grounding:              "Grounding",
  analysis:               "Analysis",
  structured_reflection:  "Structured Reflection",
  stabilization:          "Stabilization",
  extended_reasoning:     "Extended Reasoning",
  normal:                 "Normal",
};

export default function ElInsIndicator() {
  // #290 -- ONE route, the operator's default scope: a thread-tagged
  // on-demand analysis is that thread's reading and does not move this
  // badge unless the operator selects the thread. The route carries the
  // record's classification beside the mode.
  const [latest, setLatest] = useState<ElInsReasoningModeResponse | null>(null);
  const [reasoningMode, setReasoningMode] = useState<ElInsReasoningModeLabel | null>(null);
  const [hasRecentAnomaly, setHasRecentAnomaly] = useState(false);
  const [hasRecentTimelineEvent, setHasRecentTimelineEvent] = useState(false);
  const [hidden, setHidden] = useState(false);
  // #290 -- "unless the operator selects that thread": the cockpit's active
  // thread is the per-turn hook's own tag namespace, so it is the selection.
  const activeThread = useCockpit((s) => s.thread.meta?.thread_id ?? null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [m, a, t] = await Promise.all([
          getElInsReasoningMode(activeThread).catch(() => null),
          getElInsAnomalies(20).catch(() => null),
          getTimeline(20).catch(() => null),
        ]);
        if (cancelled) return;
        setLatest(m);
        if (m) setReasoningMode(m.reasoning_mode);
        if (a) {
          const cutoff = Date.now() / 1000 - ANOMALY_NEW_WINDOW_SECONDS;
          setHasRecentAnomaly(a.anomalies.some((x) => x.timestamp >= cutoff));
        }
        if (t) {
          const cutoff_ms = Date.now() - TIMELINE_NEW_WINDOW_SECONDS * 1000;
          setHasRecentTimelineEvent(t.events.some((x) => x.timestamp_ms >= cutoff_ms));
        }
      } catch {
        // Cockpit shouldn't break because of a diagnostic surface;
        // hide silently on any failure.
        if (!cancelled) setHidden(true);
      }
    })();
    return () => { cancelled = true; };
  }, [activeThread]);

  if (hidden) return null;

  const cls = latest?.ratio_classification || null;
  const label = cls ? (LABELS[cls] || cls) : "—";
  const tooltip = latest && typeof latest.el === "number" && typeof latest.ins === "number"
    ? `EL ${latest.el.toFixed(2)} · INS ${latest.ins.toFixed(2)}`
    : "no EL/INS records yet";
  const modeLabel = reasoningMode ? (MODE_LABELS[reasoningMode] || reasoningMode) : null;

  return (
    <div style={{ display: "inline-flex", flexDirection: "column", alignItems: "flex-start", gap: 2 }}>
      <Link
        to="/operator/el_ins"
        className="el-ins-indicator"
        title={tooltip}
        data-testid="el-ins-indicator"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          padding: "4px 10px",
          border: "1px solid rgba(20, 24, 28, 0.12)",
          borderRadius: 2,
          textDecoration: "none",
          color: "var(--os-text, #fff)",
          fontSize: 12,
        }}
      >
        <span
          style={{
            display: "inline-block",
            width: 8, height: 8, borderRadius: "50%",
            background: classColor(cls),
          }}
        />
        <span style={{ fontFamily: "var(--font-mono)", letterSpacing: "0.5px" }}>
          Stability: {label}
        </span>
        {hasRecentAnomaly ? (
          <Link
            to="/operator/el_ins/anomalies"
            title="Recent anomalies — open dashboard"
            data-testid="el-ins-anomaly-dot"
            onClick={(e) => e.stopPropagation()}
            style={{
              display: "inline-block",
              width: 8, height: 8, borderRadius: "50%",
              background: "var(--os-err, #ef4444)",
              marginLeft: 4,
            }}
          />
        ) : null}
        {hasRecentTimelineEvent ? (
          <Link
            to="/operator/timeline"
            title="Recent timeline events — open log"
            data-testid="el-ins-timeline-dot"
            onClick={(e) => e.stopPropagation()}
            style={{
              display: "inline-block",
              width: 8, height: 8, borderRadius: "50%",
              background: "var(--os-accent, #00f0ff)",
              marginLeft: 4,
            }}
          />
        ) : null}
      </Link>
      {modeLabel ? (
        <span
          data-testid="el-ins-reasoning-mode-label"
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--os-text-muted, #888)",
            paddingLeft: 10,
            letterSpacing: "0.5px",
          }}
        >
          {/* F -- the provider mode chosen for the next read, as such. */}
          Provider mode: {modeLabel}
        </span>
      ) : null}
    </div>
  );
}

// #374 -- routed to the one shared implementation. This copy was already
// correct (it had an explicit `balanced` arm and a muted default, so #355's
// UNMAPPED landed on grey by luck rather than by rule); the other three fell
// through to the OK green. Keeping four private copies is how that happened.
const classColor = elInsClassColor;
