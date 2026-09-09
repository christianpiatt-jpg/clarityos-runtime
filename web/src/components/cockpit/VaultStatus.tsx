// components/cockpit/VaultStatus.tsx — the vault rail.
//
// #218 (CT-1 2026-09-09) -- THE RAIL GETS QUIET. It used to render about
// twenty lines off the continuity snapshot: five counts, five coherence
// flags, eight store names, and a last episode. For a new member every one
// of them was empty — counts at 0, flags at "—", stores with no stamp,
// "last episode — · weight —". The rail was noisiest exactly when it had
// nothing to say, and that is what a member meets first.
//
// It is now ONE LINK, and above it ONE line that appears only when it is
// true: "vault · N items", where N is the sum of the snapshot's counts.
// At N = 0 the link stands alone — no zero, no dash, no empty row. An
// absence is not a reading (D5), and a rail is not the place to prove one.
//
// NOTHING WAS DELETED. The counts, the flags, the per-store stamps and the
// last episode moved to /vault (components/vault/VaultSnapshotRows.tsx),
// carrying every provenance title attribute unchanged — the hover contract
// is how CT-1 checks a row against the wire, so it travels with the row.
// The snapshot call is untouched: the cockpit already loads it, and this
// component still reads it for the one number.

import { Link } from "react-router-dom";
import type { ContinuitySnapshot } from "../../services/continuity";

export interface VaultStatusProps {
  snapshot: ContinuitySnapshot | null;
}

/** The sum of the snapshot's counts.
 *
 *  ★ WHAT THESE COUNT, AND WHY THE LINE DOES NOT SAY "vault". A refuter
 *  caught this before it shipped: snapshot.counts is the CONTINUITY
 *  envelope's collections (events · episodes · narratives · story_arcs ·
 *  elins_briefs), which grow on every member TURN. /vault lists a
 *  different store entirely -- the notes a member saves by hand. On CT-1's
 *  own captured snapshot they read 55 and 0. A line reading "vault · 55
 *  items" one line above a link to a page that says "0 items · Nothing
 *  saved yet" is exactly the kind of thing this order exists to remove,
 *  so the line names what it actually counts. The order's governing
 *  clause was "only when it is TRUE and short" -- CT-1's to reword.
 *
 *  Non-numeric and negative entries are not counts and do not contribute;
 *  the result is never NaN. */
export function itemTotal(snapshot: ContinuitySnapshot | null | undefined): number {
  const counts = snapshot?.counts ?? {};
  let n = 0;
  for (const v of Object.values(counts)) {
    if (typeof v === "number" && Number.isFinite(v) && v > 0) n += v;
  }
  return n;
}

export default function VaultStatus({ snapshot }: VaultStatusProps) {
  const n = itemTotal(snapshot);

  return (
    <div style={{ fontSize: 13 }}>
      {n > 0 && (
        <div
          data-testid="vault-total"
          title="snapshot.counts (sum)"
          style={{ color: "#666", marginBottom: 6 }}
        >
          continuity · {n} {n === 1 ? "item" : "items"}
        </div>
      )}
      <Link to="/vault" data-testid="vault-open">
        Open Vault →
      </Link>
    </div>
  );
}
