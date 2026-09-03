/**
 * AddToCorpusBox — the corpus front door in the cockpit.
 *
 * ★ WHY THIS EXISTS. Every other free-text box in the cockpit is a
 * DIAGNOSTIC: the text is analysed and discarded (or, with a thread, a
 * scalar seal is kept). This box is the one whose input is KEPT: it posts to
 * /ingest/manual, which runs ELINS v2 and stores the text + envelope in the
 * member's library with an object_vector and offers the row to the member's
 * Dewey neighborhoods -- so what enters is connectable, not just stored.
 *
 * Lives beside the Personal ELINS seed composer, same tokens, no new route,
 * no cockpitStore change: the box owns its own small state.
 *
 * ★ NO TITLE FIELD YET. The brief asked for an optional title. The server
 * contract (V54IngestManualRequest) has no title field, so a title typed
 * here would be silently dropped -- a field that lies. The field arrives with
 * the contract; until then the box asks only for what it can keep.
 */
import { useState } from "react";
import { Link } from "react-router-dom";

import { ingestManual } from "../../lib/api";

const label: React.CSSProperties = {
  fontFamily: "var(--font-mono)",
  fontSize: 10,
  color: "var(--color-text-secondary)",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  display: "block",
  marginBottom: 4,
};

const area: React.CSSProperties = {
  width: "100%",
  background: "var(--color-bg-surface-alt)",
  color: "var(--color-text-primary)",
  fontFamily: "var(--font-sans)",
  fontSize: 13,
  border: "1px solid var(--color-text-secondary)",
  borderRadius: "var(--radius-small)",
  padding: 8,
  outline: "none",
  resize: "vertical",
  boxSizing: "border-box",
};

const note: React.CSSProperties = {
  marginTop: 4,
  fontFamily: "var(--font-mono)",
  fontSize: 10,
  letterSpacing: "0.03em",
  color: "var(--color-text-secondary)",
};

// The error line takes its colour and size from .cv2-err; an inline colour
// here would override the class and render a failure in the same muted grey
// as a success note.
const errNote: React.CSSProperties = {
  marginTop: 4,
  fontFamily: "var(--font-mono)",
  letterSpacing: "0.03em",
};

export default function AddToCorpusBox() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [addedId, setAddedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = text.trim().length > 0 && !busy;

  async function submit() {
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    setAddedId(null);
    try {
      const r = await ingestManual({ text: text.trim(), source: "cockpit" });
      setAddedId(r.library_id);
      setText("");
    } catch (e) {
      // The failure is shown, never swallowed: the member pressed a button
      // that promised to keep something. The text stays -- nothing was kept.
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div data-testid="add-to-corpus" style={{ marginTop: 12 }}>
      <label htmlFor="corpus-text" style={label}>Add to corpus — kept, not just read</label>
      <textarea
        id="corpus-text"
        data-testid="corpus-text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={3}
        placeholder="Paste text you want in your library. It is analysed and stored with a vector."
        style={area}
        disabled={busy}
      />
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
        <button
          type="button"
          className="cv2-btn"
          data-testid="corpus-submit"
          onClick={submit}
          disabled={!canSubmit}
          aria-label="Add to corpus"
        >
          {busy ? "adding…" : "Add to corpus"}
        </button>
        {addedId ? (
          <span data-testid="corpus-result" style={note}>
            added · <code>{addedId}</code> ·{" "}
            {/* Router Link, not <a href>: the embed mount runs under
                HashRouter, where a raw href would send the HOST page to
                /library; standalone it would reload and drop cockpit state. */}
            <Link to="/library" style={{ color: "var(--color-text-primary)" }}>open library</Link>
          </span>
        ) : null}
        {error ? (
          <span data-testid="corpus-error" className="cv2-err" style={errNote}>{error}</span>
        ) : null}
      </div>
    </div>
  );
}
