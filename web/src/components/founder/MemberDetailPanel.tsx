// components/founder/MemberDetailPanel.tsx — search a user + view their
// membership view. Drives ManualActivateButton + DMNotesPanel +
// ELINSInspector once a user is selected.

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { founderMembersList } from "../../lib/api";

interface Props {
  selected: string;
  onSelect: (user: string) => void;
  /** #150 -- a search miss offers "create one?"; this hands the email to Create member */
  onCreateRequest?: (email: string) => void;
}

export default function MemberDetailPanel({ selected, onSelect, onCreateRequest }: Props) {
  const [search, setSearch] = useState(selected);
  // #150 -- does a doc exist for the selected address? null = unknown / not looked up.
  const [exists, setExists] = useState<boolean | null>(null);

  const submit = useCallback((ev: React.FormEvent) => {
    ev.preventDefault();
    const trimmed = search.trim();
    if (trimmed) onSelect(trimmed);
  }, [search, onSelect]);

  useEffect(() => { setSearch(selected); }, [selected]);

  useEffect(() => {
    let alive = true;
    setExists(null);
    if (!selected) return;
    founderMembersList({ email: selected })
      .then((r) => { if (alive) setExists(r.count > 0); })
      .catch(() => { if (alive) setExists(null); });  // a failed lookup says nothing
    return () => { alive = false; };
  }, [selected]);

  return (
    <section style={panelStyle}>
      <h2 style={{ margin: 0, fontSize: 16, marginBottom: 8 }}>Member search</h2>
      <form onSubmit={submit} style={{ display: "flex", gap: 8 }}>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Username (exact)"
          style={{
            flex: 1, padding: "6px 8px", fontSize: 13,
            border: "1px solid #ccc", borderRadius: 4,
          }}
          aria-label="Username"
        />
        <button type="submit" disabled={!search.trim()}>Select</button>
      </form>
      {selected && (
        <div style={{ marginTop: 8, fontSize: 13 }}>
          Selected: <code>{selected}</code>
          {" · "}
          <Link
            to={`/founder/operator/${encodeURIComponent(selected)}`}
            style={{ color: "var(--os-focus, #00F0FF)", textDecoration: "none" }}
          >
            Operator profile →
          </Link>
        </div>
      )}
      {/* only an EMAIL-shaped selection can be "no account yet": a legacy
          username that misses is not something Create member can make */}
      {selected && exists === false && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(selected) && (
        <div style={{ marginTop: 8, fontSize: 13 }} data-testid="member-miss">
          No account yet for <code>{selected}</code> — create one?{" "}
          <button type="button" onClick={() => onCreateRequest?.(selected)} data-testid="member-miss-create">
            Create
          </button>
        </div>
      )}
    </section>
  );
}

const panelStyle: React.CSSProperties = {
  border: "1px solid #ddd",
  borderRadius: 6,
  padding: 12,
  background: "#fff",
  marginBottom: 12,
};
