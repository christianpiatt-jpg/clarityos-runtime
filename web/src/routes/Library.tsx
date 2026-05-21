// Server-authoritative library. Reads from GET /library/list, writes via
// POST /library/write, edits via POST /library/update. No delete in spec.
//
// Mirror of Vault but: title is required, content is Markdown-format (we
// show it as plain text for v1; a renderer can land later without changing
// the storage shape).

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  type ServerLibraryItem,
  type UsageEnvelope,
  libraryUserList,
  libraryUserUpdate,
  libraryUserWrite,
} from "../lib/api";

type Mode = "view" | "compose" | "edit";

interface Draft {
  title: string;
  content: string;
  tagsInput: string;
}

const EMPTY_DRAFT: Draft = { title: "", content: "", tagsInput: "" };

export default function Library() {
  const [items, setItems] = useState<ServerLibraryItem[]>([]);
  const [active, setActive] = useState<ServerLibraryItem | null>(null);
  const [mode, setMode] = useState<Mode>("view");
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usage, setUsage] = useState<UsageEnvelope | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await libraryUserList(200);
      setItems(r.items);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  function startNew() {
    setActive(null);
    setDraft(EMPTY_DRAFT);
    setMode("compose");
    setError(null);
  }

  function clickItem(item: ServerLibraryItem) {
    setActive(item);
    setMode("view");
    setError(null);
  }

  function startEdit() {
    if (!active) return;
    setDraft({
      title: active.title || "",
      content: active.content || "",
      tagsInput: (active.tags || []).join(", "),
    });
    setMode("edit");
    setError(null);
  }

  function cancel() {
    setMode("view");
    setDraft(EMPTY_DRAFT);
    setError(null);
  }

  async function save() {
    if (busy) return;
    if (!draft.title.trim()) {
      setError("Title is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const tags = draft.tagsInput
        .split(",")
        .map((t) => t.trim())
        .filter((t) => t.length > 0);
      if (mode === "compose") {
        const r = await libraryUserWrite({
          title: draft.title.trim(),
          content: draft.content,
          tags,
        });
        setUsage(r.usage);
        setActive(r.item);
      } else if (mode === "edit" && active) {
        const r = await libraryUserUpdate({
          id: active.id,
          title: draft.title.trim(),
          content: draft.content,
          tags,
        });
        setUsage(r.usage);
        setActive(r.item);
      }
      setMode("view");
      setDraft(EMPTY_DRAFT);
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="panel">
        <div className="row row-between" style={{ alignItems: "flex-start" }}>
          <div>
            <h1>LIBRARY</h1>
            <p className="muted" style={{ marginTop: 4 }}>
              Authored entries. Markdown content.{" "}
              <span className="mono" style={{ color: "var(--os-text-tertiary)" }}>
                {items.length} item{items.length === 1 ? "" : "s"}
              </span>
              {usage ? (
                <>
                  {" · "}
                  <span className="mono" style={{ color: "var(--os-text-tertiary)" }}>
                    {formatBytes(usage.bytes_used)} / {formatBytes(usage.quota)}
                  </span>
                </>
              ) : null}
            </p>
          </div>
          <button
            className="btn btn-sm"
            onClick={startNew}
            disabled={busy || mode !== "view"}
          >
            + NEW
          </button>
        </div>
      </div>

      {error ? <div className="banner err">{error}</div> : null}

      <div className="panel-grid">
        <div>
          {loading ? (
            <div className="empty">Loading…</div>
          ) : items.length === 0 ? (
            <div className="empty">No library entries yet. Click + NEW to add one.</div>
          ) : (
            items.map((item) => (
              <button
                key={item.id}
                className="list-item"
                style={{
                  width: "100%",
                  textAlign: "left",
                  background: active?.id === item.id ? "var(--os-elevated)" : undefined,
                  borderColor: active?.id === item.id ? "var(--os-focus)" : undefined,
                  cursor: "pointer",
                }}
                onClick={() => clickItem(item)}
              >
                <div className="row row-between">
                  <span className="tag cyan">library</span>
                  <span className="dim mono" style={{ fontSize: "0.7rem" }}>
                    {new Date(item.created_at * 1000).toLocaleString()}
                  </span>
                </div>
                <div className="title" style={{ marginTop: 6 }}>
                  {item.title || "(untitled)"}
                </div>
                {item.tags && item.tags.length > 0 ? (
                  <div className="meta" style={{ marginTop: 6 }}>{item.tags.join(", ")}</div>
                ) : null}
              </button>
            ))
          )}
        </div>

        <div>
          {mode === "compose" || mode === "edit" ? (
            <div className="panel" style={{ marginBottom: 0 }}>
              <h3>{mode === "compose" ? "NEW LIBRARY ENTRY" : "EDIT LIBRARY ENTRY"}</h3>
              <div className="field">
                <label htmlFor="lt">Title (required)</label>
                <input
                  id="lt"
                  className="input"
                  type="text"
                  value={draft.title}
                  onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="lc">Content (Markdown)</label>
                <textarea
                  id="lc"
                  className="input"
                  rows={16}
                  value={draft.content}
                  onChange={(e) => setDraft({ ...draft, content: e.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor="ltg">Tags (comma-separated, optional)</label>
                <input
                  id="ltg"
                  className="input"
                  type="text"
                  value={draft.tagsInput}
                  onChange={(e) => setDraft({ ...draft, tagsInput: e.target.value })}
                />
              </div>
              <div className="row" style={{ gap: 8 }}>
                <button className="btn" onClick={save} disabled={busy || !draft.title.trim()}>
                  {busy ? <span className="spinner" /> : "SAVE"}
                </button>
                <button className="btn btn-secondary" onClick={cancel} disabled={busy}>
                  CANCEL
                </button>
              </div>
            </div>
          ) : !active ? (
            <div className="empty">Pick an entry to view, or click + NEW to add one.</div>
          ) : (
            <div className="panel" style={{ marginBottom: 0 }}>
              <div className="row row-between" style={{ alignItems: "flex-start" }}>
                <h3 style={{ margin: 0 }}>{active.title}</h3>
                <button
                  className="btn btn-sm btn-secondary"
                  onClick={startEdit}
                  disabled={busy}
                >
                  EDIT
                </button>
              </div>
              <div className="kv" style={{ marginTop: 12, marginBottom: 12 }}>
                <div className="k">created</div>
                <div className="v">{new Date(active.created_at * 1000).toLocaleString()}</div>
                <div className="k">updated</div>
                <div className="v">{new Date(active.updated_at * 1000).toLocaleString()}</div>
                {active.tags?.length ? (
                  <>
                    <div className="k">tags</div>
                    <div className="v">{active.tags.join(", ")}</div>
                  </>
                ) : null}
                <div className="k">size</div>
                <div className="v">{formatBytes(active.size_bytes)}</div>
              </div>
              <pre className="output">{active.content}</pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
}
