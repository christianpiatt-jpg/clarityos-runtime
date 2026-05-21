// web/src/routes/FounderPisPiss.tsx
//
// Phase 13C addition. Renders the read-only PIS / PISS dual-surface
// taxonomic identity view. Reads:
//   GET /founder/identity/pis-piss
//
// Renamed from the literal Phase 13 spec's `FounderIdentity.tsx`
// because Phase 8C already shipped `FounderIdentity.tsx` for the
// distinct "identity coherence" layer. The two coexist as siblings
// under the /founder/identity namespace:
//   /founder/identity            -> FounderIdentity.tsx       (Phase 8C)
//   /founder/identity/pis-piss   -> FounderPisPiss.tsx        (Phase 13C)
//
// No new libraries.

import { useEffect, useState, useCallback } from "react";
import { Link, useLocation } from "react-router-dom";

interface PisDescription {
  name: string;
  expanded: string;
  purpose: string;
  components: string[];
  guarantees: string[];
  boundaries: string[];
}

interface PissDescription {
  name: string;
  expanded: string;
  purpose: string;
  surfaces: string[];
  guarantees: string[];
  boundaries: string[];
}

interface SharedConcept {
  concept: string;
  source: string;
  surface: string;
}

interface RelationshipBlock {
  directionality: string;
  shared_concepts: SharedConcept[];
  load_bearing_property: string;
}

interface PisPissResponse {
  pis: PisDescription | Record<string, never>;
  piss: PissDescription | Record<string, never>;
  relationship: RelationshipBlock | Record<string, never>;
  notes: string[];
  errors?: Record<string, string>;
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...(init ?? {}),
  });
  if (!res.ok) throw new Error(`${path} → ${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

function VerificationBanner() {
  const loc = useLocation();
  if (new URLSearchParams(loc.search).get("verify") !== "1") return null;
  return (
    <div
      role="status"
      className="acceptance-verify-banner"
      style={{
        padding: "0.5rem 0.75rem", marginBottom: "1rem",
        border: "1px solid currentColor", fontSize: "0.85rem",
      }}
    >
      Verification Mode — <code>?verify=1</code> active. Reading
      {" "}<code>/founder/identity/pis-piss</code>; taxonomy is in
      {" "}<code>pis_piss_identity.py</code> at repo root. The
      descriptions are static and intentionally do not change with
      acceptance records.
    </div>
  );
}

function HalfCard({
  title, expanded, purpose,
  itemsHeader, items,
  guarantees, boundaries,
}: {
  title: string;
  expanded?: string;
  purpose?: string;
  itemsHeader: string;
  items?: string[];
  guarantees?: string[];
  boundaries?: string[];
}) {
  return (
    <section style={{
      border: "1px solid currentColor", padding: "1rem",
      borderRadius: 0, height: "100%",
    }}>
      <h2 style={{ marginTop: 0 }}>
        {title}{expanded ? <span style={{ opacity: 0.65, fontSize: "0.8em" }}> · {expanded}</span> : null}
      </h2>
      {purpose && (
        <p style={{ marginTop: "0.25rem", opacity: 0.85 }}>{purpose}</p>
      )}
      <h3 style={{ marginBottom: "0.25rem" }}>{itemsHeader}</h3>
      {items && items.length > 0 ? (
        <ul style={{ paddingLeft: "1.25rem", marginTop: 0 }}>
          {items.map((it, i) => (
            <li key={i} style={{ fontSize: "0.9rem", marginBottom: "0.15rem" }}>
              <code style={{ fontSize: "0.85rem" }}>{it}</code>
            </li>
          ))}
        </ul>
      ) : (
        <p style={{ opacity: 0.6, fontSize: "0.85rem" }}>
          (no description available)
        </p>
      )}
      <h3 style={{ marginBottom: "0.25rem" }}>Guarantees</h3>
      {guarantees && guarantees.length > 0 ? (
        <ul style={{ paddingLeft: "1.25rem", marginTop: 0 }}>
          {guarantees.map((g, i) => (
            <li key={i} style={{ fontSize: "0.9rem", marginBottom: "0.15rem" }}>
              {g}
            </li>
          ))}
        </ul>
      ) : (
        <p style={{ opacity: 0.6, fontSize: "0.85rem" }}>—</p>
      )}
      <h3 style={{ marginBottom: "0.25rem" }}>Boundaries</h3>
      {boundaries && boundaries.length > 0 ? (
        <ul style={{ paddingLeft: "1.25rem", marginTop: 0 }}>
          {boundaries.map((b, i) => (
            <li key={i} style={{ fontSize: "0.9rem", marginBottom: "0.15rem" }}>
              {b}
            </li>
          ))}
        </ul>
      ) : (
        <p style={{ opacity: 0.6, fontSize: "0.85rem" }}>—</p>
      )}
    </section>
  );
}

function RelationshipSection({ rel }: { rel: RelationshipBlock | Record<string, never> }) {
  const directionality = "directionality" in rel ? rel.directionality : null;
  const lbp = "load_bearing_property" in rel ? rel.load_bearing_property : null;
  const shared = ("shared_concepts" in rel && rel.shared_concepts)
    ? rel.shared_concepts
    : [];
  return (
    <section style={{ marginTop: "1.5rem" }}>
      <h2>Relationship</h2>
      {directionality && (
        <p>
          <strong>directionality:</strong> {directionality}
        </p>
      )}
      <h3>Shared concepts (PIS → PISS)</h3>
      {shared.length > 0 ? (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left" }}>concept</th>
              <th style={{ textAlign: "left" }}>source (PIS)</th>
              <th style={{ textAlign: "left" }}>surface (PISS)</th>
            </tr>
          </thead>
          <tbody>
            {shared.map((s, i) => (
              <tr key={i}>
                <td><code>{s.concept}</code></td>
                <td><code style={{ fontSize: "0.85rem" }}>{s.source}</code></td>
                <td><code style={{ fontSize: "0.85rem" }}>{s.surface}</code></td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p style={{ opacity: 0.6 }}>(no shared concepts described)</p>
      )}
      {lbp && (
        <p style={{ marginTop: "0.75rem", opacity: 0.85 }}>
          <strong>load-bearing property:</strong> {lbp}
        </p>
      )}
    </section>
  );
}

function NotesList({ notes }: { notes: string[] }) {
  if (!notes || notes.length === 0) {
    return <p style={{ opacity: 0.6 }}>(no notes)</p>;
  }
  return (
    <ul style={{ paddingLeft: "1.25rem" }}>
      {notes.map((n, i) => (
        <li key={i} style={{ fontSize: "0.9rem" }}>
          <code>{n}</code>
        </li>
      ))}
    </ul>
  );
}

export default function FounderPisPiss() {
  const [data, setData] = useState<PisPissResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const j = await api<PisPissResponse>("/founder/identity/pis-piss");
      setData(j);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <main style={{ padding: "1.5rem", maxWidth: 1100, margin: "0 auto" }}>
      <p style={{ marginBottom: "1rem" }}>
        <Link to="/founder">← founder console</Link>
        {" · "}
        <Link to="/founder/identity">identity coherence (Phase 8C)</Link>
      </p>
      <h1>PIS / PISS — Dual-Surface Taxonomy</h1>
      <VerificationBanner />
      {loading && <p>loading…</p>}
      {err && (
        <p role="alert" style={{ color: "crimson" }}>
          error: {err}
        </p>
      )}
      {data && (
        <>
          <section style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "1rem",
            marginTop: "1.5rem",
            alignItems: "stretch",
          }}>
            <HalfCard
              title={"name" in data.pis ? data.pis.name : "PIS"}
              expanded={"expanded" in data.pis ? data.pis.expanded : undefined}
              purpose={"purpose" in data.pis ? data.pis.purpose : undefined}
              itemsHeader="Components"
              items={"components" in data.pis ? data.pis.components : []}
              guarantees={"guarantees" in data.pis ? data.pis.guarantees : []}
              boundaries={"boundaries" in data.pis ? data.pis.boundaries : []}
            />
            <HalfCard
              title={"name" in data.piss ? data.piss.name : "PISS"}
              expanded={"expanded" in data.piss ? data.piss.expanded : undefined}
              purpose={"purpose" in data.piss ? data.piss.purpose : undefined}
              itemsHeader="Surfaces"
              items={"surfaces" in data.piss ? data.piss.surfaces : []}
              guarantees={"guarantees" in data.piss ? data.piss.guarantees : []}
              boundaries={"boundaries" in data.piss ? data.piss.boundaries : []}
            />
          </section>

          <RelationshipSection rel={data.relationship} />

          <section style={{ marginTop: "1.5rem" }}>
            <h2>Notes</h2>
            <NotesList notes={data.notes ?? []} />
          </section>

          {data.errors && (
            <section style={{ marginTop: "1rem", color: "crimson" }}>
              <h3>Errors</h3>
              <pre style={{ fontSize: "0.85rem" }}>
                {JSON.stringify(data.errors, null, 2)}
              </pre>
            </section>
          )}

          <section style={{ marginTop: "1.5rem", opacity: 0.75 }}>
            <p style={{ fontSize: "0.85rem" }}>
              This view is a static taxonomic description. It does not
              read acceptance records, does not change with run state,
              and does not gate, predict, or automate. Update only when
              the top-level taxonomy itself changes.
            </p>
          </section>
        </>
      )}
    </main>
  );
}
