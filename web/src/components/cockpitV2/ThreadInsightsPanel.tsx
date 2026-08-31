/**
 * ThreadInsightsPanel — the /threads InsightsPanel, ported into CockpitV2.
 *
 * Three tabs, mirroring routes/Threads.tsx:565-780 exactly:
 *   Thread  — message count, updated-at, the stored dated summary, and the
 *             SUMMARIZE / RENAME / DELETE actions.
 *   ELINS   — mounts the shared v1 ElinsV2View against the composed
 *             transcript (POST /elins/v2/run).
 *   Physics — mounts the shared v1 EmotionalPhysicsView against the same
 *             transcript (POST /me/emotional_physics/analyze).
 *
 * Both views are self-driving: give them `runOn` / `text` and they fire their
 * own request on mount, handing the result back through onRun / onAnalyze. We
 * cache that result in the store's thread slice so switching tabs away and
 * back does not re-run the kernel; the cache clears whenever a new turn is
 * sent, because the kernel inputs are transcript-keyed.
 *
 * Styling is cv2-* only (styles/cockpitV2.css). None of Threads.tsx's inline
 * style objects are imported — only the shared, self-styling badge module and
 * the shared v1 views are reused.
 */
import { useMemo, useState } from "react";

import { useCockpit, cockpit, type InsightsTab } from "../../state/cockpitStore";
import ElinsV2View from "../v1/ElinsV2View/ElinsV2View";
import EmotionalPhysicsView from "../v1/EmotionalPhysicsView/EmotionalPhysicsView";

const TABS: { id: InsightsTab; label: string }[] = [
  { id: "thread", label: "Thread" },
  { id: "elins", label: "ELINS" },
  { id: "physics", label: "Physics" },
];

/** Same relative formatting Threads.tsx uses for updated/summary stamps. */
function relativeTime(ts: number | null | undefined): string {
  if (!ts) return "—";
  // ThreadMeta.updated_at is seconds; summary_ts_ms is milliseconds.
  const ms = ts > 1e11 ? ts : ts * 1000;
  const delta = Math.max(0, Date.now() - ms);
  const mins = Math.floor(delta / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function ThreadInsightsPanel() {
  const thread = useCockpit((s) => s.thread);
  const { meta, messages, tab, busy, elins, physics } = thread;

  const [renaming, setRenaming] = useState(false);
  const [renameDraft, setRenameDraft] = useState("");

  // Compose the transcript once per messages change. Capped to 6KB so we
  // don't blow the backend's text limit — same cap as Threads.tsx:283-292.
  const threadText = useMemo(
    () =>
      messages
        .map((m) => `${m.role}: ${m.content}`)
        .join("\n")
        .slice(0, 6000)
        .trim(),
    [messages],
  );

  // Only pass runOn when there is text, so the views render their empty
  // state instead of firing a request against the empty string.
  const runOn = threadText ? { rawText: threadText, region: null } : null;

  async function commitRename(): Promise<void> {
    await cockpit.thread.actions.rename(renameDraft.trim());
    setRenaming(false);
  }

  if (!meta) {
    return (
      <section className="cv2-panel cv2-panel-insights">
        <header className="cv2-panel-head">Insights</header>
        <div className="cv2-panel-body">
          <p className="cv2-muted">No thread selected.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="cv2-panel cv2-panel-insights">
      <header className="cv2-panel-head">Insights</header>
      <div className="cv2-panel-body">
        <div role="tablist" aria-label="Insights view selector" className="cv2-tabs" data-testid="insights-tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              data-testid={`insights-tab-${t.id}`}
              className={"cv2-tab" + (tab === t.id ? " is-active" : "")}
              onClick={() => cockpit.thread.actions.setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === "thread" ? (
          <>
            <dl className="cv2-kv">
              <div className="cv2-kv-row">
                <dt>messages</dt>
                <dd>{meta.message_count}</dd>
              </div>
              <div className="cv2-kv-row">
                <dt>updated</dt>
                <dd>{relativeTime(meta.updated_at)}</dd>
              </div>
              {meta.summary_ts_ms ? (
                <div className="cv2-kv-row">
                  <dt>summary</dt>
                  <dd>{relativeTime(meta.summary_ts_ms)}</dd>
                </div>
              ) : null}
            </dl>

            {renaming ? (
              <div className="cv2-card">
                <div className="cv2-card-head">Rename thread</div>
                <input
                  className="cv2-input"
                  type="text"
                  value={renameDraft}
                  autoFocus
                  aria-label="Thread title"
                  onChange={(e) => setRenameDraft(e.target.value)}
                />
                <div className="cv2-actions-row">
                  <button
                    type="button"
                    className="cv2-btn cv2-btn-primary"
                    disabled={busy}
                    onClick={() => void commitRename()}
                  >
                    {busy ? "Saving…" : "SAVE"}
                  </button>
                  <button
                    type="button"
                    className="cv2-btn"
                    disabled={busy}
                    onClick={() => setRenaming(false)}
                  >
                    CANCEL
                  </button>
                </div>
              </div>
            ) : meta.summary ? (
              <div className="cv2-card" data-testid="thread-summary-card">
                <div className="cv2-card-head">Summary</div>
                <div className="cv2-card-body">{meta.summary}</div>
              </div>
            ) : (
              <p className="cv2-muted">No summary yet.</p>
            )}

            {!renaming ? (
              <div className="cv2-actions">
                <button
                  type="button"
                  className="cv2-btn"
                  disabled={busy}
                  onClick={() => void cockpit.thread.actions.summarize()}
                >
                  {busy ? "…" : "SUMMARIZE"}
                </button>
                <button
                  type="button"
                  className="cv2-btn"
                  disabled={busy}
                  onClick={() => {
                    setRenameDraft(meta.title ?? "");
                    setRenaming(true);
                  }}
                >
                  RENAME
                </button>
                <button
                  type="button"
                  className="cv2-btn cv2-btn-danger"
                  disabled={busy}
                  onClick={() => void cockpit.thread.actions.remove()}
                >
                  DELETE
                </button>
              </div>
            ) : null}
          </>
        ) : tab === "elins" ? (
          runOn ? (
            <ElinsV2View
              envelope={elins}
              runOn={runOn}
              onRun={cockpit.thread.actions.setElins}
            />
          ) : (
            <p className="cv2-muted" data-testid="insights-elins-empty">
              No messages yet — add a turn to run ELINS on this thread.
            </p>
          )
        ) : runOn ? (
          <EmotionalPhysicsView
            response={physics}
            text={runOn.rawText}
            onAnalyze={cockpit.thread.actions.setPhysics}
          />
        ) : (
          <p className="cv2-muted" data-testid="insights-physics-empty">
            No messages yet — add a turn to analyse this thread.
          </p>
        )}
      </div>
    </section>
  );
}
