// components/shared/DirectiveBadges.tsx
//
// A19/A30 — the read-only directive surface badges, extracted verbatim from
// routes/Threads.tsx so both the /threads route and the CockpitV2 ChatPanel
// render an identical badge from an identical payload. Behaviour, markup,
// test ids and styles are unchanged from the Threads originals.
//
// Both badges are self-contained: they style themselves with the global
// v1 tokens (--font-mono / --color-accent-cyan), so they carry no dependency
// on either surface's layout CSS.

import { type DirectiveMeta, type GroundingStatus } from "../../lib/api";

// A19/A30 — view-model: a thread message plus the per-turn directive surface.
// grounding_status (cite, A19) + directive_metadata (all directives, A30) ride
// on the live POST response, not on the stored message, so they're present
// only for turns sent this session and absent for messages rehydrated via
// getThread.
export type DirectiveSurface = {
  grounding_status?: GroundingStatus | null;
  directive_metadata?: Record<string, DirectiveMeta> | null;
};

/** True when a message carries anything the badge row should render.
 *  Mirrors the Threads.tsx:823-825 guard exactly: cite is covered by the
 *  GroundingBadge, so directive_metadata alone only counts for non-cite keys. */
export function hasDirectiveSurface(m: DirectiveSurface): boolean {
  return Boolean(
    m.grounding_status ||
      (m.directive_metadata &&
        Object.keys(m.directive_metadata).some((k) => k !== "cite")),
  );
}

/** The non-cite directive keys, in payload order. */
export function nonCiteDirectives(m: DirectiveSurface): string[] {
  return m.directive_metadata
    ? Object.keys(m.directive_metadata).filter((k) => k !== "cite")
    : [];
}

// A19 — small read-only badge surfacing the #cite grounding outcome.
// Renders nothing for non-#cite turns (null/undefined). Colors follow the
// A19 card: OK → #2ECC71, Incomplete → #E74C3C. (A18 emits only these two
// states; there is no distinct "retried" status to show.)
export function GroundingBadge({ status }: { status?: GroundingStatus | null }) {
  if (status !== "grounded" && status !== "incomplete") return null;
  const ok = status === "grounded";
  const color = ok ? "#2ECC71" : "#E74C3C";
  const label = ok ? "Grounding: OK" : "Grounding: Incomplete";
  const tip = ok
    ? "Output passed grounding validation."
    : "Grounding failed after retry cap.";
  return (
    <span
      data-testid="grounding-badge"
      data-grounding={status}
      title={tip}
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: 10,
        color,
        border: `1px solid ${color}`,
        borderRadius: 3,
        padding: "0 6px",
        lineHeight: "16px",
        letterSpacing: "0.04em",
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </span>
  );
}

// A30 — unified read-only badge for a non-cite directive (cite keeps its own
// GroundingBadge above). Renders "<Label>: <status>" in the accent color.
const _DIRECTIVE_LABEL: Record<string, string> = {
  structure: "Structure",
  primitives: "Primitives",
  regression: "Regression",
  compare: "Compare",
  reduce: "Reduce",
  operator: "Operator",
};
export function DirectiveBadge({ name, status }: { name: string; status?: string | null }) {
  const label = _DIRECTIVE_LABEL[name] ?? name;
  const text = status ? `${label}: ${status}` : label;
  return (
    <span
      data-testid="directive-badge"
      data-directive={name}
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: 10,
        color: "var(--color-accent-cyan)",
        border: "1px solid var(--color-accent-cyan)",
        borderRadius: 3,
        padding: "0 6px",
        lineHeight: "16px",
        letterSpacing: "0.04em",
        whiteSpace: "nowrap",
      }}
    >
      {text}
    </span>
  );
}
