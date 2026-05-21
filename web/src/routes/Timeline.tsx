// Timeline — vertical chronological view of system-generated events.
// Server is the only source of truth. Reads from GET /timeline/list.
//
// Events are emitted by the backend on vault/library writes (kind values:
// vault.write, vault.update, vault.delete, library.write, library.update);
// ELINS ingestion will emit too once that surface ships.
//
// Filters: kind (dropdown, populated from loaded events) + since/until date.

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  type ServerTimelineEvent,
  timelineList,
} from "../lib/api";

interface Filters {
  kind: string;
  sinceDate: string;
  untilDate: string;
}

const EMPTY_FILTERS: Filters = { kind: "", sinceDate: "", untilDate: "" };

export default function Timeline() {
  const [events, setEvents] = useState<ServerTimelineEvent[]>([]);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (f: Filters) => {
    setLoading(true);
    setError(null);
    try {
      const r = await timelineList({
        kind: f.kind || undefined,
        since: f.sinceDate ? Date.parse(f.sinceDate) / 1000 : undefined,
        until: f.untilDate ? Date.parse(f.untilDate + "T23:59:59") / 1000 : undefined,
        limit: 200,
      });
      setEvents(r.events);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(filters); }, [refresh, filters]);

  // Dropdown options derived from currently-loaded events; "all" first,
  // then known kinds. New kinds appear as they're encountered.
  const knownKinds = useMemo(() => {
    const set = new Set<string>();
    events.forEach((e) => set.add(e.kind));
    return Array.from(set).sort();
  }, [events]);

  return (
    <div>
      <div className="panel">
        <h1>TIMELINE</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          System-generated events. Vault writes, library writes, and ingestion
          activity append here automatically.{" "}
          <span className="mono" style={{ color: "var(--os-text-tertiary)" }}>
            {events.length} event{events.length === 1 ? "" : "s"}
          </span>
        </p>
      </div>

      <div className="panel">
        <div className="row" style={{ gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="field" style={{ marginBottom: 0, minWidth: 180 }}>
            <label htmlFor="tl-kind">Kind</label>
            <select
              id="tl-kind"
              className="input"
              value={filters.kind}
              onChange={(e) => setFilters({ ...filters, kind: e.target.value })}
            >
              <option value="">all</option>
              {knownKinds.map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label htmlFor="tl-since">From</label>
            <input
              id="tl-since"
              className="input"
              type="date"
              value={filters.sinceDate}
              onChange={(e) => setFilters({ ...filters, sinceDate: e.target.value })}
            />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label htmlFor="tl-until">To</label>
            <input
              id="tl-until"
              className="input"
              type="date"
              value={filters.untilDate}
              onChange={(e) => setFilters({ ...filters, untilDate: e.target.value })}
            />
          </div>
          {(filters.kind || filters.sinceDate || filters.untilDate) ? (
            <button
              className="btn btn-sm btn-secondary"
              onClick={() => setFilters(EMPTY_FILTERS)}
            >
              CLEAR
            </button>
          ) : null}
        </div>
      </div>

      {error ? <div className="banner err">{error}</div> : null}

      {loading ? (
        <div className="empty">Loading…</div>
      ) : events.length === 0 ? (
        <div className="empty">
          No events match. Vault and library writes will appear here automatically.
        </div>
      ) : (
        <div>
          {events.map((ev) => (
            <div
              key={ev.id}
              className="list-item"
              style={{ width: "100%", textAlign: "left" }}
            >
              <div className="row row-between">
                <span className={`tag ${kindTone(ev.kind)}`}>{ev.kind}</span>
                <span className="dim mono" style={{ fontSize: "0.7rem" }}>
                  {new Date(ev.ts * 1000).toLocaleString()}
                </span>
              </div>
              <div className="title" style={{ marginTop: 6 }}>
                {ev.summary || "(no summary)"}
              </div>
              {ev.ref ? (
                <div className="meta" style={{ marginTop: 6 }}>
                  ref: <span className="mono">{ev.ref}</span>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function kindTone(kind: string): string {
  if (kind.startsWith("vault.")) return "cyan";
  if (kind.startsWith("library.")) return "red";
  if (kind.startsWith("elins.")) return "amber";
  return "";
}
