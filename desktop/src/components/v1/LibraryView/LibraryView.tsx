// desktop/src/components/v1/LibraryView/LibraryView.tsx
//
// Browse-only view over the user's personal library
// (GET /library/list). Two-pane: list on top with filters, detail
// below. 320px-compatible (vertical stack), expands gracefully when
// surfaced via CenterColumn at wider widths.
//
// Filters (deterministic, client-side):
//   - tag select: dropdown of every distinct tag present in the
//                 returned items, plus "all"
//   - time range: all / 7d / 30d / 1y
//   - text search: matches against title (case-insensitive)
//
// No mutation. /library/write, /library/update, /library/delete are
// deliberately not exposed here — this slice is browse-only.

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  listLibrary,
  type LibraryItem,
} from "../../../lib/library";
import { ApiError } from "../../../lib/api";
import styles from "./LibraryView.module.css";

type TimeRange = "all" | "7d" | "30d" | "1y";

const TIME_RANGE_LABEL: Record<TimeRange, string> = {
  all: "all time",
  "7d": "last 7 days",
  "30d": "last 30 days",
  "1y": "last year",
};

const DAY_SECONDS = 86400;
const TIME_RANGE_WINDOW_SECONDS: Record<Exclude<TimeRange, "all">, number> = {
  "7d":  7 * DAY_SECONDS,
  "30d": 30 * DAY_SECONDS,
  "1y":  365 * DAY_SECONDS,
};

interface Props {
  /** Optional cap on the initial list fetch. Server clamps to 500. */
  initialLimit?: number;
}

export default function LibraryView({ initialLimit = 100 }: Props) {
  const [items, setItems] = useState<LibraryItem[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tagFilter, setTagFilter] = useState<string>("__all__");
  const [timeRange, setTimeRange] = useState<TimeRange>("all");
  const [query, setQuery] = useState<string>("");

  const doFetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await listLibrary(initialLimit);
      setItems(r.items);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [initialLimit]);

  useEffect(() => {
    void doFetch();
  }, [doFetch]);

  // Distinct tag set, sorted.
  const allTags = useMemo(() => {
    if (!items) return [];
    const s = new Set<string>();
    for (const it of items) {
      for (const t of it.tags ?? []) {
        if (typeof t === "string" && t.trim().length > 0) s.add(t.trim());
      }
    }
    return Array.from(s).sort();
  }, [items]);

  // Filtered list. created_at is float seconds.
  const filtered = useMemo(() => {
    if (!items) return [];
    const now = Date.now() / 1000;
    const window =
      timeRange === "all"
        ? null
        : TIME_RANGE_WINDOW_SECONDS[timeRange];
    const cutoff = window === null ? -Infinity : now - window;
    const q = query.trim().toLowerCase();

    return items.filter((it) => {
      if (tagFilter !== "__all__") {
        if (!Array.isArray(it.tags) || !it.tags.includes(tagFilter)) return false;
      }
      if (cutoff !== -Infinity) {
        const ts = typeof it.created_at === "number" ? it.created_at : 0;
        if (ts < cutoff) return false;
      }
      if (q.length > 0) {
        if (!(it.title || "").toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [items, tagFilter, timeRange, query]);

  // Auto-select first filtered item when the current selection drops out.
  useEffect(() => {
    if (!filtered.length) {
      if (selectedId !== null) setSelectedId(null);
      return;
    }
    if (!selectedId || !filtered.some((i) => i.id === selectedId)) {
      setSelectedId(filtered[0].id);
    }
  }, [filtered, selectedId]);

  const selected = useMemo(
    () => filtered.find((i) => i.id === selectedId) ?? null,
    [filtered, selectedId],
  );

  return (
    <section className={styles.root} aria-label="Library view">
      <header className={styles.heading}>
        <span className={styles.title}>Library</span>
        <span className={styles.subtitle}>
          {items
            ? `${filtered.length} of ${items.length}`
            : loading
              ? "loading…"
              : error
                ? "error"
                : "—"}
        </span>
      </header>

      {/* Filters */}
      <div className={styles.filters}>
        <input
          type="search"
          className={styles.searchInput}
          placeholder="search titles…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search library titles"
        />
        <div className={styles.filterRow}>
          <label className={styles.filterLabel}>
            <span>tag</span>
            <select
              className={styles.select}
              value={tagFilter}
              onChange={(e) => setTagFilter(e.target.value)}
              aria-label="Filter by tag"
            >
              <option value="__all__">all</option>
              {allTags.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </label>
          <label className={styles.filterLabel}>
            <span>time</span>
            <select
              className={styles.select}
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value as TimeRange)}
              aria-label="Filter by time range"
            >
              {(["all", "7d", "30d", "1y"] as const).map((r) => (
                <option key={r} value={r}>{TIME_RANGE_LABEL[r]}</option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {/* Error / empty / list states */}
      {error ? (
        <div role="alert" className={styles.error}>{error}</div>
      ) : !items && loading ? (
        <div className={styles.empty}>loading library…</div>
      ) : !items ? (
        <div className={styles.empty}>—</div>
      ) : filtered.length === 0 ? (
        <div className={styles.empty}>
          {items.length === 0
            ? "library is empty"
            : "no entries match these filters"}
        </div>
      ) : (
        <ul className={styles.list} role="listbox" aria-label="Library entries">
          {filtered.map((it) => {
            const active = it.id === selectedId;
            return (
              <li key={it.id}>
                <button
                  type="button"
                  className={active ? styles.listItemActive : styles.listItem}
                  onClick={() => setSelectedId(it.id)}
                  role="option"
                  aria-selected={active}
                >
                  <span className={styles.itemTitle}>
                    {(it.title || "").trim() || "Untitled"}
                  </span>
                  <span className={styles.itemMeta}>
                    {formatDate(it.created_at)}
                    {Array.isArray(it.tags) && it.tags.length > 0
                      ? ` · ${it.tags.slice(0, 3).join(", ")}${it.tags.length > 3 ? "…" : ""}`
                      : ""}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {/* Detail pane */}
      {selected ? (
        <DetailPane item={selected} />
      ) : items && filtered.length > 0 ? (
        <div className={styles.empty}>select an entry to view its content</div>
      ) : null}

      <footer className={styles.footer}>
        <button
          type="button"
          className={styles.actionBtn}
          onClick={doFetch}
          disabled={loading}
          aria-label="Refresh library list"
        >
          {loading ? "refreshing…" : "Refresh"}
        </button>
      </footer>
    </section>
  );
}

// -----------------------------------------------------------------
// Sub-blocks
// -----------------------------------------------------------------

function DetailPane({ item }: { item: LibraryItem }) {
  const tags = Array.isArray(item.tags) ? item.tags : [];
  return (
    <article className={styles.detail} aria-label={`Library entry ${item.title}`}>
      <header className={styles.detailHeader}>
        <h3 className={styles.detailTitle}>
          {(item.title || "").trim() || "Untitled"}
        </h3>
        <div className={styles.detailMeta}>
          <span>created {formatDate(item.created_at)}</span>
          {item.updated_at && item.updated_at !== item.created_at ? (
            <span> · updated {formatDate(item.updated_at)}</span>
          ) : null}
          {typeof item.size_bytes === "number" ? (
            <span> · {formatBytes(item.size_bytes)}</span>
          ) : null}
        </div>
        {tags.length > 0 ? (
          <div className={styles.tagRow}>
            {tags.map((t) => (
              <span key={t} className={styles.tag}>{t}</span>
            ))}
          </div>
        ) : null}
      </header>

      <pre className={styles.body}>{item.content || ""}</pre>
    </article>
  );
}

// -----------------------------------------------------------------
// Utils
// -----------------------------------------------------------------

function formatDate(tsSec: number | undefined): string {
  if (typeof tsSec !== "number" || !isFinite(tsSec) || tsSec <= 0) return "—";
  const d = new Date(tsSec * 1000);
  return d.toISOString().slice(0, 10);
}

function formatBytes(n: number): string {
  if (!isFinite(n) || n < 0) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
