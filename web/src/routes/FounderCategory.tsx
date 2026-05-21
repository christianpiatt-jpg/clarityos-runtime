// web/src/routes/FounderCategory.tsx
//
// Phase 14C addition. Renders the read-only category-definition +
// external-language view. Reads:
//   GET /founder/identity/category
//
// Sibling to FounderPisPiss (Phase 13C) and FounderIdentity (Phase 8C)
// under the /founder/identity/* namespace.
//
// No new libraries.

import { useEffect, useState, useCallback } from "react";
import { Link, useLocation } from "react-router-dom";

interface CategoryDescription {
  name: string;
  acronym: string;
  instance: string;
  purpose: string;
  structural_properties: string[];
  boundaries: string[];
  differentiators: Record<string, string>;
  non_goals: string[];
}

interface ExampleStatement {
  kind: string;
  text: string;
}

interface ExternalLanguage {
  allowed: string[];
  disallowed: string[];
}

interface CategoryResponse {
  category: CategoryDescription | Record<string, never>;
  example_statements: ExampleStatement[];
  external_language: ExternalLanguage | Record<string, never>;
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
      {" "}<code>/founder/identity/category</code>; taxonomy is in
      {" "}<code>category_definition.py</code> at repo root. The
      descriptions are static and do not change with acceptance records.
    </div>
  );
}

function PropertyList({ title, items }: { title: string; items: string[] }) {
  return (
    <section style={{ marginTop: "1rem" }}>
      <h3 style={{ marginBottom: "0.25rem" }}>{title}</h3>
      {items && items.length > 0 ? (
        <ul style={{ paddingLeft: "1.25rem", marginTop: 0 }}>
          {items.map((it, i) => (
            <li key={i} style={{ fontSize: "0.9rem", marginBottom: "0.15rem" }}>
              {it}
            </li>
          ))}
        </ul>
      ) : (
        <p style={{ opacity: 0.6, fontSize: "0.85rem" }}>—</p>
      )}
    </section>
  );
}

function DifferentiatorsTable({
  diffs,
}: {
  diffs: Record<string, string>;
}) {
  const entries = Object.entries(diffs || {});
  if (entries.length === 0) {
    return <p style={{ opacity: 0.6 }}>(no differentiators recorded)</p>;
  }
  // Make the keys human-readable: vs_productivity_tools -> "vs productivity tools"
  const humanize = (k: string) => k.replace(/^vs_/, "vs. ").replace(/_/g, " ");
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr>
          <th style={{ textAlign: "left", width: "30%" }}>differentiator</th>
          <th style={{ textAlign: "left" }}>distinction</th>
        </tr>
      </thead>
      <tbody>
        {entries.map(([k, v]) => (
          <tr key={k}>
            <td><code>{humanize(k)}</code></td>
            <td style={{ fontSize: "0.9rem" }}>{v}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function StatementsList({ items }: { items: ExampleStatement[] }) {
  if (!items || items.length === 0) {
    return <p style={{ opacity: 0.6 }}>(no example statements)</p>;
  }
  return (
    <div>
      {items.map((s, i) => (
        <blockquote
          key={i}
          style={{
            margin: "0.5rem 0",
            padding: "0.75rem 1rem",
            borderLeft: "3px solid currentColor",
            opacity: 0.95,
          }}
        >
          <div style={{ fontSize: "0.75rem", opacity: 0.6, marginBottom: 4 }}>
            <code>{s.kind}</code>
          </div>
          <div style={{ fontSize: "0.95rem", lineHeight: 1.5 }}>{s.text}</div>
        </blockquote>
      ))}
    </div>
  );
}

function ExternalLanguageTable({
  lang,
}: {
  lang: ExternalLanguage | Record<string, never>;
}) {
  const allowed = ("allowed" in lang ? lang.allowed : []) || [];
  const disallowed = ("disallowed" in lang ? lang.disallowed : []) || [];
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr>
          <th style={{ textAlign: "left", width: "50%" }}>allowed</th>
          <th style={{ textAlign: "left" }}>disallowed</th>
        </tr>
      </thead>
      <tbody>
        {Array.from({ length: Math.max(allowed.length, disallowed.length) }).map(
          (_, i) => (
            <tr key={i}>
              <td style={{ fontSize: "0.9rem", verticalAlign: "top" }}>
                {allowed[i] ?? ""}
              </td>
              <td style={{ fontSize: "0.9rem", verticalAlign: "top" }}>
                {disallowed[i] ?? ""}
              </td>
            </tr>
          )
        )}
      </tbody>
    </table>
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

export default function FounderCategory() {
  const [data, setData] = useState<CategoryResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const j = await api<CategoryResponse>("/founder/identity/category");
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
        {" · "}
        <Link to="/founder/identity/pis-piss">PIS / PISS (Phase 13C)</Link>
      </p>
      <h1>Category Definition + External Language</h1>
      <VerificationBanner />
      {loading && <p>loading…</p>}
      {err && (
        <p role="alert" style={{ color: "crimson" }}>
          error: {err}
        </p>
      )}
      {data && (
        <>
          <section style={{ marginTop: "1.5rem" }}>
            <h2>
              {"name" in data.category ? data.category.name : "Inferential Discipline System"}
              {" "}
              <span style={{ opacity: 0.6, fontSize: "0.7em" }}>
                ({"acronym" in data.category ? data.category.acronym : "IDS"})
              </span>
            </h2>
            {"instance" in data.category && (
              <p style={{ opacity: 0.85 }}>
                Reference instance: <code>{data.category.instance}</code>
              </p>
            )}
            {"purpose" in data.category && (
              <p style={{ marginTop: "0.5rem" }}>{data.category.purpose}</p>
            )}
          </section>

          <PropertyList
            title="Structural properties (define category membership)"
            items={"structural_properties" in data.category ? data.category.structural_properties : []}
          />

          <PropertyList
            title="Boundaries (the category does NOT)"
            items={"boundaries" in data.category ? data.category.boundaries : []}
          />

          <section style={{ marginTop: "1.5rem" }}>
            <h3>Differentiators</h3>
            <DifferentiatorsTable
              diffs={"differentiators" in data.category ? data.category.differentiators : {}}
            />
          </section>

          <PropertyList
            title="Non-goals"
            items={"non_goals" in data.category ? data.category.non_goals : []}
          />

          <section style={{ marginTop: "1.5rem" }}>
            <h2>Example external statements</h2>
            <p style={{ opacity: 0.75, fontSize: "0.9rem" }}>
              Each is operator-grade: no outcome promises, no predictions,
              no claims of effectiveness.
            </p>
            <StatementsList items={data.example_statements ?? []} />
          </section>

          <section style={{ marginTop: "1.5rem" }}>
            <h2>External language — allowed / disallowed</h2>
            <ExternalLanguageTable lang={data.external_language} />
          </section>

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
              This view is a static taxonomic description of the category.
              It does not read acceptance records, does not change with run
              state, and does not gate, predict, or automate. Update only
              when the category boundary itself changes.
            </p>
          </section>
        </>
      )}
    </main>
  );
}
