// Iframe surface — Bridge to external pages inside the operator cockpit.
//
// Loads an arbitrary URL inside an <iframe> so the operator can interact
// with WordPress admin, internal tools, or any embeddable page without
// leaving ClarityOS. URL is taken from ?src=<encoded> or from a saved
// localStorage list of bookmarks.
//
// IMPORTANT: Most public sites set X-Frame-Options: DENY or a
// frame-ancestors CSP directive, which prevents embedding. This surface
// is most useful for self-hosted tools you control (your WordPress
// admin, internal dashboards, etc.). When a site refuses to frame, the
// browser shows a blank pane — the surface displays a hint when this
// is likely.

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

const BOOKMARKS_KEY = "clarityos_iframe_bookmarks";
const LAST_URL_KEY = "clarityos_iframe_last_url";

interface Bookmark {
  label: string;
  url: string;
}

function loadBookmarks(): Bookmark[] {
  try {
    const raw = localStorage.getItem(BOOKMARKS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (b: unknown): b is Bookmark =>
        typeof b === "object" &&
        b !== null &&
        typeof (b as Bookmark).label === "string" &&
        typeof (b as Bookmark).url === "string",
    );
  } catch {
    return [];
  }
}

function saveBookmarks(bs: Bookmark[]): void {
  try {
    localStorage.setItem(BOOKMARKS_KEY, JSON.stringify(bs));
  } catch {
    /* storage disabled */
  }
}

function normalizeUrl(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  // Allow about:blank as a way to explicitly clear the frame.
  if (trimmed === "about:blank") return trimmed;
  // Reject anything that isn't http(s) — javascript: / data: URLs in an
  // iframe are a footgun and we don't need them here.
  try {
    const u = new URL(/^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`);
    if (u.protocol !== "http:" && u.protocol !== "https:") return null;
    return u.toString();
  } catch {
    return null;
  }
}

export default function Iframe() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialSrc = useMemo(() => {
    const fromQuery = searchParams.get("src");
    if (fromQuery) return normalizeUrl(fromQuery);
    try {
      const last = localStorage.getItem(LAST_URL_KEY);
      if (last) return last;
    } catch {
      /* noop */
    }
    return null;
  }, []); // resolve once on mount

  const [url, setUrl] = useState<string | null>(initialSrc);
  const [draft, setDraft] = useState<string>(initialSrc ?? "");
  const [bookmarks, setBookmarks] = useState<Bookmark[]>(() => loadBookmarks());
  const [newLabel, setNewLabel] = useState("");
  const [iframeKey, setIframeKey] = useState(0); // bump to force reload
  const [loadedAt, setLoadedAt] = useState<number | null>(null);

  // Persist last URL whenever it changes successfully.
  useEffect(() => {
    if (!url) return;
    try {
      localStorage.setItem(LAST_URL_KEY, url);
    } catch {
      /* noop */
    }
  }, [url]);

  function go() {
    const normalized = normalizeUrl(draft);
    if (!normalized) return;
    setUrl(normalized);
    setDraft(normalized);
    setLoadedAt(null);
    setIframeKey((k) => k + 1);
    // Reflect in URL so the surface is shareable / refreshable.
    setSearchParams({ src: normalized }, { replace: true });
  }

  function clear() {
    setUrl(null);
    setDraft("");
    setLoadedAt(null);
    setSearchParams({}, { replace: true });
  }

  function reload() {
    setLoadedAt(null);
    setIframeKey((k) => k + 1);
  }

  function addBookmark() {
    const normalized = normalizeUrl(draft);
    if (!normalized) return;
    const label = newLabel.trim() || new URL(normalized).hostname;
    const next = [...bookmarks.filter((b) => b.url !== normalized), { label, url: normalized }];
    setBookmarks(next);
    saveBookmarks(next);
    setNewLabel("");
  }

  function removeBookmark(idx: number) {
    const next = bookmarks.filter((_, i) => i !== idx);
    setBookmarks(next);
    saveBookmarks(next);
  }

  function openBookmark(b: Bookmark) {
    setUrl(b.url);
    setDraft(b.url);
    setLoadedAt(null);
    setIframeKey((k) => k + 1);
    setSearchParams({ src: b.url }, { replace: true });
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div className="panel" style={{ marginBottom: 12 }}>
        <h1>IFRAME</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          External page bridge. Load WordPress admin, internal tools, or any
          embeddable URL inside the cockpit. Sites that send <code>X-Frame-Options: DENY</code>{" "}
          or restrict <code>frame-ancestors</code> will refuse to load — that is the host's
          policy, not a bug here.
        </p>
      </div>

      <div className="panel" style={{ marginBottom: 12 }}>
        <div className="field">
          <label htmlFor="iframe-url">URL</label>
          <input
            id="iframe-url"
            className="input"
            type="url"
            placeholder="https://pro-mediations.com/wp-admin/"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") go();
            }}
          />
        </div>
        <div className="row" style={{ marginTop: 8 }}>
          <button className="btn" onClick={go} disabled={!normalizeUrl(draft)}>
            LOAD
          </button>
          <button className="btn btn-secondary btn-sm" onClick={reload} disabled={!url}>
            RELOAD
          </button>
          <button className="btn btn-secondary btn-sm" onClick={clear} disabled={!url}>
            CLEAR
          </button>
          <div style={{ flex: 1 }} />
          <input
            className="input"
            type="text"
            placeholder="bookmark label (optional)"
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            style={{ maxWidth: 240 }}
          />
          <button
            className="btn btn-sm"
            onClick={addBookmark}
            disabled={!normalizeUrl(draft)}
          >
            SAVE BOOKMARK
          </button>
        </div>
      </div>

      {bookmarks.length > 0 && (
        <div className="panel" style={{ marginBottom: 12 }}>
          <h2 style={{ margin: 0, marginBottom: 8 }}>BOOKMARKS</h2>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {bookmarks.map((b, i) => (
              <div
                key={`${b.url}-${i}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  border: "1px solid var(--os-border, rgba(255,255,255,0.15))",
                  borderRadius: 4,
                  padding: "4px 8px",
                }}
              >
                <button
                  className="btn btn-sm btn-secondary"
                  onClick={() => openBookmark(b)}
                  style={{ border: "none", background: "transparent", padding: 0 }}
                  title={b.url}
                >
                  {b.label}
                </button>
                <button
                  className="btn btn-sm btn-secondary"
                  onClick={() => removeBookmark(i)}
                  title="Remove bookmark"
                  style={{ padding: "0 6px" }}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div
        className="panel"
        style={{
          flex: 1,
          minHeight: 400,
          display: "flex",
          flexDirection: "column",
          padding: 0,
          overflow: "hidden",
        }}
      >
        {!url ? (
          <div className="empty" style={{ padding: 24 }}>
            No URL loaded. Enter a URL above and press LOAD, or open a bookmark.
          </div>
        ) : (
          <>
            <div
              className="muted"
              style={{
                padding: "6px 12px",
                fontSize: "0.8rem",
                fontFamily: "var(--font-mono)",
                borderBottom: "1px solid var(--os-border, rgba(255,255,255,0.1))",
                display: "flex",
                gap: 12,
              }}
            >
              <span>src: {url}</span>
              {loadedAt && <span>loaded {new Date(loadedAt).toLocaleTimeString()}</span>}
            </div>
            <iframe
              key={iframeKey}
              src={url}
              title="ClarityOS iframe surface"
              style={{ flex: 1, width: "100%", border: "none", background: "#fff" }}
              // Allow same-origin so logged-in WP admin sessions work, plus
              // scripts/forms for normal page interaction. Adjust per host.
              sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-downloads"
              referrerPolicy="no-referrer-when-downgrade"
              onLoad={() => setLoadedAt(Date.now())}
            />
          </>
        )}
      </div>
    </div>
  );
}
