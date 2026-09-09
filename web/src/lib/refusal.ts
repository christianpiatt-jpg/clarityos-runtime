/**
 * #238 (CT-1 2026-09-09, measured on his own member session) -- A REFUSAL
 * DOES NOT GET A FORECAST.
 *
 * WHAT THE MEMBER SAW. Section 1 refused correctly on 52 characters of seed
 * text: every bearing "unclear", the prose "Cannot assess internal pattern
 * without concrete context." Then, on the SAME screen, section 3 printed
 * "P0 risk 33% · P1 0% · P2 0% · P3 22%" and section 4 printed "Soft
 * pressure rising. Watch the edge for fragmentation." Percentages and a
 * directional sentence over an input the layer above had just said it could
 * not assess.
 *
 * THE FLAG WAS NEVER LOST. `no_signal` is on the wire at
 * pipeline.L10_signature.summary.no_signal (ELINS/standard_elins.py builds it
 * into the output object; ELINS/elins_v2_view.py maps that to L10_signature)
 * and the v1 rail already reads it (ElinsV2View, #110c). The Personal ELINS
 * sections simply never looked. Nothing dropped it mid-hop, so nothing about
 * the backend changes: this module is the missing read.
 *
 * TWO LAYERS CAN DECLINE, and either one silences what sits below it:
 *
 *   physics   the relational-primitives reader declines by saying so in its
 *             own enum -- "unclear" IS the word for it
 *             (intelligence_kernel.py: `"unclear" — the reader declined`),
 *             and a MISSING key is the same kind. When no bearing carries a
 *             substantive reading, the reader declined wholesale.
 *             The reason is quoted from the layer that EXPLAINS the
 *             decline, which the live capture shows is field_curvature --
 *             see REASON_LAYERS below.
 *   elins     synthesis sets no_signal when every primitive intensity is
 *             0.0 (ELINS/standard_elins.py). #110(c): that flag must survive
 *             the hop.
 *
 * WHAT A CALLER DOES WITH IT: renders the panel, carrying ONE sentence -- the
 * reason, in the same words the layer above used -- and NO value. Never a
 * recomputed default, never a 0%, never a phrase assembled from an empty
 * envelope. The panel does not disappear: a member must see that it exists
 * and why it is quiet.
 */

import { BEARING_KEYS } from "./api";
import type { EmotionalPhysicsResponse, ElinsV2Envelope } from "./api";

export interface Refusal {
  /** True when a layer above declined and nothing below it may speak. */
  refused: boolean;
  /** The reason, in the declining layer's own words. Null when not refused. */
  reason: string | null;
  /** Which layer declined — for the title attribute, never for prose. */
  source: "physics" | "elins" | null;
}

const NOT_REFUSED: Refusal = { refused: false, reason: null, source: null };

/** The word the physics enums use for "the reader declined". */
export const DECLINED = "unclear";

/** ★ A refuter caught this: the comment here used to claim these were
 *  "#110c's own words, reused". They are not. The v1 rail says
 *  "no signal — <instrument>" (ElinsV2View). This is the rail's PHRASE,
 *  set as a sentence for a panel that has room for one -- but it is
 *  wording ET-1 chose, and the order said not to invent any. Named in the
 *  return for CT-1 to replace or approve. */
export const ELINS_NO_SIGNAL_REASON = "No signal in this reading.";

/** The fallback when the reader declined but wrote no prose. Short, and it
 *  claims nothing about why.
 *  ★ NEW WORDING, not CT-1's. It reaches a member only when every layer
 *  declined AND none wrote a note. Named in the return for CT-1 to replace. */
export const PHYSICS_DECLINED_REASON = "The reading above could not assess this input.";

/** The order in which the physics layers are asked for the reason.
 *
 *  ★ MEASURED, not guessed. On the live capture of CT-1's own session the
 *  sentence he quoted -- "No specific situation provided. Cannot assess
 *  internal pattern without concrete context." -- is field_curvature's note.
 *  relational_primitives carries a different and much longer one about
 *  there being no second party, which is a poor answer to "why is the
 *  collapse forecast quiet". Reading the bearings but quoting the field
 *  curvature is deliberate: the bearings are where a decline is DETECTED,
 *  the curvature note is where it is EXPLAINED. */
const REASON_LAYERS = ["field_curvature", "edge_pressure", "relational_primitives"] as const;

function declineReason(ep: EmotionalPhysicsResponse): string {
  const src = ep as unknown as Record<string, unknown>;
  for (const layer of REASON_LAYERS) {
    const notes = obj(src[layer]).notes;
    if (typeof notes === "string" && notes.trim()) return notes.trim();
  }
  return "";
}

function obj(v: unknown): Record<string, unknown> {
  return v !== null && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

/**
 * Did the relational-primitives reader decline wholesale?
 *
 * Every bearing reading "unclear" is the reader saying, in its own vocabulary,
 * that it could not assess. One or two unclear bearings are a real partial
 * reading and are NOT a refusal — the whole set is.
 */
export function physicsRefusal(ep: EmotionalPhysicsResponse | null | undefined): Refusal {
  if (!ep) return NOT_REFUSED;
  const rp = obj(ep.relational_primitives);
  // ★ MISSING AND "unclear" ARE THE SAME KIND HERE, and requiring all five
  // keys PRESENT was a hole a refuter drove a whole forecast through: four
  // bearings declining plus ONE dropped key read as "not refused", and §3
  // printed 33% again. The backend already scores a missing field and an
  // "unclear" one identically as non-substantive (intelligence_kernel.py,
  // the substantive-enum block), so this reads the layer the way the layer
  // is defined. It also closes the parse_error case, where every layer
  // arrives {} and the sections below used to speak with full confidence.
  const substantive = BEARING_KEYS.filter((k) => {
    const v = rp[k];
    return typeof v === "string" && v.trim() && v.trim().toLowerCase() !== DECLINED;
  });
  if (substantive.length > 0) return NOT_REFUSED;
  return {
    refused: true,
    reason: declineReason(ep) || PHYSICS_DECLINED_REASON,
    source: "physics",
  };
}

/**
 * Did ELINS synthesis find no signal? The flag rides in the pipeline bag at
 * L10_signature.summary.no_signal — the same place the v1 rail reads it.
 */
export function elinsRefusal(elins: ElinsV2Envelope | null | undefined): Refusal {
  if (!elins) return NOT_REFUSED;
  const summary = obj(obj(obj(elins.pipeline).L10_signature).summary);
  if (summary.no_signal !== true) return NOT_REFUSED;
  return { refused: true, reason: ELINS_NO_SIGNAL_REASON, source: "elins" };
}

/**
 * The ONE reading the sections below section 1 gate on. Physics is checked
 * first because it is the layer above on the member's screen, and CT-1's rule
 * is that the reason appears in the same words that layer used.
 */
export function sectionRefusal(
  ep: EmotionalPhysicsResponse | null | undefined,
  elins: ElinsV2Envelope | null | undefined,
): Refusal {
  const physics = physicsRefusal(ep);
  if (physics.refused) return physics;
  return elinsRefusal(elins);
}
