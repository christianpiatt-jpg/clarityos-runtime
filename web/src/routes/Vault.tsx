// Server-authoritative vault. Reads from GET /vault/list, writes via
// POST /vault/write, edits via POST /vault/update, deletes via
// POST /vault/delete. No localStorage.

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  type ServerVaultItem,
  type UsageEnvelope,
  vaultDelete,
  vaultList,
  vaultUpdate,
  vaultWrite,
} from "../lib/api";

type Mode = "view" | "compose" | "edit";

interface Draft {
  title: string;
  content: string;
  tagsInput: string;
}

const EMPTY_DRAFT: Draft = { title: "", content: "", tagsInput: "" };

export default function Vault() {
  const [items, setItems] = useState<ServerVaultItem[]>([]);
  const [active, setActive] = useState<ServerVaultItem | null>(null);
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
      const r = await vaultList(200);
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

  function clickItem(item: ServerVaultItem) {
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
    setBusy(true);
    setError(null);
    try {
      const tags = draft.tagsInput
        .split(",")
        .map((t) => t.trim())
        .filter((t) => t.length > 0);
      if (mode === "compose") {
        const r = await vaultWrite({
          title: draft.title.trim(),
          content: draft.content,
          tags,
        });
        setUsage(r.usage);
        setActive(r.item);
      } else if (mode === "edit" && active) {
        const r = await vaultUpdate({
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

  async function remove() {
    if (!active || busy) return;
    // eslint-disable-next-line no-alert
    if (!window.confirm(`Delete "${displayTitle(active)}"? This cannot be undone.`)) return;
    setBusy(true);
    setError(null);
    try {
      const r = await vaultDelete(active.id);
      setUsage(r.usage);
      setActive(null);
      setMode("view");
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
            <h1>VAULT</h1>
            <p className="muted" style={{ marginTop: 4 }}>
              Server-authoritative notes and session transcripts.{" "}
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
            <div className="empty">Nothing saved yet. Click + NEW to add a note.</div>
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
                  <span className={`tag ${item.type === "note" ? "cyan" : "red"}`}>
                    {item.type}
                  </span>
                  <span className="dim mono" style={{ fontSize: "0.7rem" }}>
                    {new Date(item.created_at * 1000).toLocaleString()}
                  </span>
                </div>
                <div className="title" style={{ marginTop: 6 }}>{displayTitle(item)}</div>
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
              <h3>{mode === "compose" ? "NEW VAULT NOTE" : "EDIT VAULT NOTE"}</h3>
              <div className="field">
                <label htmlFor="vt">Title</label>
                <input
                  id="vt"
                  className="input"
                  type="text"
                  value={draft.title}
                  onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor="vc">Content</label>
                <textarea
                  id="vc"
                  className="input"
                  rows={12}
                  value={draft.content}
                  onChange={(e) => setDraft({ ...draft, content: e.target.value })}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="vtg">Tags (comma-separated, optional)</label>
                <input
                  id="vtg"
                  className="input"
                  type="text"
                  value={draft.tagsInput}
                  onChange={(e) => setDraft({ ...draft, tagsInput: e.target.value })}
                />
              </div>
              <div className="row" style={{ gap: 8 }}>
                <button
                  className="btn"
                  onClick={save}
                  disabled={busy || !draft.content.trim()}
                >
                  {busy ? <span className="spinner" /> : "SAVE"}
                </button>
                <button className="btn btn-secondary" onClick={cancel} disabled={busy}>
                  CANCEL
                </button>
              </div>
            </div>
          ) : !active ? (
            <div className="empty">Pick an item to view, or click + NEW to add one.</div>
          ) : (
            <div className="panel" style={{ marginBottom: 0 }}>
              <div className="row row-between" style={{ alignItems: "flex-start" }}>
                <h3 style={{ margin: 0 }}>{displayTitle(active)}</h3>
                <div className="row" style={{ gap: 8 }}>
                  <button
                    className="btn btn-sm btn-secondary"
                    onClick={startEdit}
                    disabled={busy}
                  >
                    EDIT
                  </button>
                  <button
                    className="btn btn-sm btn-secondary"
                    onClick={remove}
                    disabled={busy}
                  >
                    DELETE
                  </button>
                </div>
              </div>
              <div className="kv" style={{ marginTop: 12, marginBottom: 12 }}>
                <div className="k">type</div>
                <div className="v">{active.type}</div>
                <div className="k">created</div>
                <div className="v">{new Date(active.created_at * 1000).toLocaleString()}</div>
                {active.updated_at && active.updated_at !== active.created_at ? (
                  <>
                    <div className="k">updated</div>
                    <div className="v">{new Date(active.updated_at * 1000).toLocaleString()}</div>
                  </>
                ) : null}
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

function displayTitle(item: ServerVaultItem): string {
  if (item.title && item.title.trim()) return item.title;
  if (!item.content) return "(empty)";
  const line = item.content.split("\n").find((l) => l.trim()) || item.content;
  return line.length > 80 ? line.slice(0, 80) + "…" : line;
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
}
