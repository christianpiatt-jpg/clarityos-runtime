// components/founder/CommentGeneratorPanel.tsx — #cmt UI.
//
// Renders an inline form (input + optional domain hint), calls
// /cmt/generate, and shows the four constructed segments + activation
// metadata + the assembled comment.

import { useCallback, useState } from "react";
import { cmtGenerate, type V33CommentResult } from "../../lib/api";

const DOMAINS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "", label: "(auto)" },
  { value: "legal", label: "legal" },
  { value: "institutional", label: "institutional" },
  { value: "economic", label: "economic" },
  { value: "geopolitical", label: "geopolitical" },
  { value: "social", label: "social" },
  { value: "personal", label: "personal" },
  { value: "technological", label: "technological" },
  { value: "ecological", label: "ecological" },
];

export default function CommentGeneratorPanel() {
  const [text, setText] = useState("");
  const [domain, setDomain] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<V33CommentResult | null>(null);

  const run = useCallback(async () => {
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await cmtGenerate(text.trim(), domain || undefined);
      setResult(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [text, domain]);

  return (
    <section style={panelStyle}>
      <h2 style={{ margin: 0, fontSize: 16, marginBottom: 8 }}>#cmt — Most Relevant Comment</h2>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste the post / quote / statement you want to comment on."
        rows={4}
        maxLength={8000}
        style={{ ...inputStyle, resize: "vertical" }}
        aria-label="Input text"
      />
      <div style={{ display: "flex", gap: 8, marginTop: 6, alignItems: "center" }}>
        <label style={{ fontSize: 12 }}>Domain hint:</label>
        <select
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          style={{ padding: "4px 6px", fontSize: 12 }}
          aria-label="Domain hint"
        >
          {DOMAINS.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
        </select>
        <button onClick={() => void run()} disabled={busy || !text.trim()}>
          {busy ? "Generating…" : "Generate comment"}
        </button>
      </div>

      {error && (
        <div style={errorStyle}>{error}</div>
      )}

      {result && (
        <div style={{ marginTop: 12 }}>
          <h3 style={{ fontSize: 13, margin: "0 0 6px 0" }}>Comment</h3>
          <div style={{
            padding: 8, background: "#fafafa", border: "1px solid #eee",
            borderRadius: 4, fontSize: 14, lineHeight: 1.5,
          }}>
            {result.comment}
          </div>

          <details style={{ marginTop: 8 }}>
            <summary style={{ cursor: "pointer", fontSize: 12, color: "#555" }}>Detection</summary>
            <pre style={preStyle}>{JSON.stringify(result.detection, null, 2)}</pre>
          </details>
          <details style={{ marginTop: 4 }}>
            <summary style={{ cursor: "pointer", fontSize: 12, color: "#555" }}>Construction (4 segments)</summary>
            <pre style={preStyle}>{JSON.stringify(result.construction, null, 2)}</pre>
          </details>
          <details style={{ marginTop: 4 }}>
            <summary style={{ cursor: "pointer", fontSize: 12, color: "#555" }}>Activation</summary>
            <pre style={preStyle}>{JSON.stringify(result.activation, null, 2)}</pre>
          </details>
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

const inputStyle: React.CSSProperties = {
  display: "block",
  width: "100%",
  padding: "6px 8px",
  fontSize: 13,
  border: "1px solid #ccc",
  borderRadius: 4,
  boxSizing: "border-box",
};

const preStyle: React.CSSProperties = {
  background: "#fafafa",
  padding: 6,
  fontSize: 11,
  overflow: "auto",
  maxHeight: 200,
  margin: 0,
};

const errorStyle: React.CSSProperties = {
  padding: 6,
  background: "#fee",
  border: "1px solid #f99",
  borderRadius: 4,
  fontSize: 12,
  marginTop: 8,
};
