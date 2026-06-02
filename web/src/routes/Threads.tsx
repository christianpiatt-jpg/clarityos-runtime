// v48 — Threads UI. Surface 4 (web v54-era): rendered as a
// full-viewport v1 ClarityOSSurface via WebShell. The /threads route
// is intentionally placed OUTSIDE the Layout wrapper in App.tsx so
// the v1 surface owns the chrome (TopBar / OperatorSidebar /
// CenterColumn / InsightsPanel) without nesting under the cockpit's
// topbar / rail / footer.
//
// All hooks / state / handlers are byte-equivalent to the v48 + v50
// implementation; only the return JSX has been restructured to feed
// WebShell's three slot props (sidebar / center / insights).

import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { useNavigate } from "react-router-dom";
import {
  ApiError,
  createThread,
  deleteThread,
  getThread,
  listThreads,
  postThreadMessage,
  renameThread,
  summarizeThread,
  type GroundingStatus,
  type ThreadMessage,
  type ThreadMeta,
} from "../lib/api";
import type { ElinsV2Envelope } from "../lib/elinsV2";
import type { EmotionalPhysicsResponse } from "../lib/emotionalPhysics";
import {
  getAuthSnapshot,
  signOut,
  subscribeAuth,
} from "../lib/auth";
import WebShell from "../components/WebShell";
import ElinsV2View from "../components/v1/ElinsV2View/ElinsV2View";
import EmotionalPhysicsView from "../components/v1/EmotionalPhysicsView/EmotionalPhysicsView";

// A19 — view-model: a thread message plus the per-turn #cite grounding
// outcome. grounding_status rides on the live POST response, not on the
// stored message, so it's present only for turns sent this session and
// absent (undefined) for messages rehydrated via getThread.
type ChatMessage = ThreadMessage & { grounding_status?: GroundingStatus | null };

// ---------- Auth subscription (mirrors Layout.tsx pattern) ----------
function useAuth() {
  return useSyncExternalStore(subscribeAuth, getAuthSnapshot, getAuthSnapshot);
}

export default function Threads() {
  const auth = useAuth();
  const navigate = useNavigate();

  const [threads, setThreads] = useState<ThreadMeta[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeMeta, setActiveMeta] = useState<ThreadMeta | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const [listLoading, setListLoading] = useState(true);
  const [threadLoading, setThreadLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [composer, setComposer] = useState<string>("");
  const [renaming, setRenaming] = useState<boolean>(false);
  const [renameDraft, setRenameDraft] = useState<string>("");

  // v54-followup — per-thread ELINS v2 envelope + Emotional Physics
  // response, cached so toggling away from a tab and back doesn't
  // re-fetch. Both clear on thread switch (kernel inputs are thread-
  // keyed, so old results are stale).
  const [threadElinsEnv, setThreadElinsEnv] =
    useState<ElinsV2Envelope | null>(null);
  const [threadEpRes, setThreadEpRes] =
    useState<EmotionalPhysicsResponse | null>(null);

  // Active tab inside the InsightsPanel. THREAD is the default (the
  // legacy meta + summary + action buttons surface). ELINS and PHYSICS
  // mount the v1 ELINS v2 and Emotional Physics views respectively,
  // wired against the active thread's composed transcript.
  type InsightsTab = "thread" | "elins" | "physics";
  const [insightsTab, setInsightsTab] = useState<InsightsTab>("thread");

  const onNavigate = useCallback((label: string) => {
    if (label === "Threads") navigate("/threads");
    if (label === "Personal ELINS") navigate("/personal-elins");
  }, [navigate]);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  function scrollToBottom() {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }

  // ---------------- Thread list ----------------
  const refreshList = useCallback(async () => {
    setListLoading(true);
    setError(null);
    try {
      const t = await listThreads();
      const sorted = [...t].sort(
        (a, b) => (b.updated_at || 0) - (a.updated_at || 0),
      );
      setThreads(sorted);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => { void refreshList(); }, [refreshList]);

  // ---------------- Active thread ----------------
  const loadThread = useCallback(async (thread_id: string) => {
    setThreadLoading(true);
    setError(null);
    try {
      const r = await getThread(thread_id);
      setActiveMeta(r.meta);
      setMessages(r.messages);
      setTimeout(scrollToBottom, 0);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      setActiveMeta(null);
      setMessages([]);
    } finally {
      setThreadLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedId) {
      void loadThread(selectedId);
    } else {
      setActiveMeta(null);
      setMessages([]);
      setRenaming(false);
    }
    // Clear cached ELINS + EP results whenever the active thread
    // changes; the kernel inputs are thread-keyed, so old results are
    // stale. Tab selection persists across thread switches.
    setThreadElinsEnv(null);
    setThreadEpRes(null);
  }, [selectedId, loadThread]);

  function selectThread(id: string) {
    setSelectedId(id);
    setComposer("");
    setRenaming(false);
    setError(null);
  }

  // ---------------- Mutators ----------------
  async function handleNewThread() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const meta = await createThread(null);
      await refreshList();
      setSelectedId(meta.thread_id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleSend() {
    if (!selectedId) return;
    const trimmed = composer.trim();
    if (!trimmed) return;
    if (sending) return;

    setSending(true);
    setError(null);
    try {
      const r = await postThreadMessage(selectedId, trimmed);
      setActiveMeta(r.meta);
      // A19 — carry the turn's grounding outcome onto the assistant
      // message so Bubble can render the badge. null on non-#cite turns.
      setMessages((cur) => [
        ...cur,
        r.user_message,
        { ...r.assistant_message, grounding_status: r.grounding_status ?? null },
      ]);
      setComposer("");
      setThreads((cur) => {
        const others = cur.filter((t) => t.thread_id !== r.meta.thread_id);
        return [r.meta, ...others];
      });
      setTimeout(scrollToBottom, 0);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setSending(false);
    }
  }

  function startRename() {
    if (!activeMeta) return;
    setRenameDraft(activeMeta.title || "");
    setRenaming(true);
    setError(null);
  }

  function cancelRename() {
    setRenaming(false);
    setRenameDraft("");
  }

  async function commitRename() {
    if (!activeMeta || busy) return;
    const next = renameDraft.trim();
    setBusy(true);
    setError(null);
    try {
      const meta = await renameThread(activeMeta.thread_id, next);
      setActiveMeta(meta);
      setThreads((cur) =>
        cur.map((t) => (t.thread_id === meta.thread_id ? meta : t)),
      );
      setRenaming(false);
      setRenameDraft("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!activeMeta || busy) return;
    const display = displayTitle(activeMeta);
    // eslint-disable-next-line no-alert
    if (!window.confirm(`Delete "${display}"? This cannot be undone.`)) return;
    setBusy(true);
    setError(null);
    try {
      await deleteThread(activeMeta.thread_id);
      const removedId = activeMeta.thread_id;
      setActiveMeta(null);
      setMessages([]);
      setSelectedId(null);
      setThreads((cur) => cur.filter((t) => t.thread_id !== removedId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleSummarize() {
    if (!activeMeta || busy) return;
    setBusy(true);
    setError(null);
    try {
      const meta = await summarizeThread(activeMeta.thread_id);
      setActiveMeta(meta);
      setThreads((cur) =>
        cur.map((t) => (t.thread_id === meta.thread_id ? meta : t)),
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  // Compose the active thread's transcript once per messages change.
  // Cap to 6KB so we don't blow the backend's text limit. Empty string
  // when there are no messages yet (the views then render their empty
  // state without firing a request).
  const threadText = useMemo(() => {
    const composed = messages
      .map((m) => `${m.role}: ${m.content}`)
      .join("\n")
      .slice(0, 6000);
    return composed.trim();
  }, [messages]);

  // ---------------- Composer keyboard handling ----------------
  function onComposerKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      void handleSend();
    }
  }

  // ---------------- Slot content ----------------
  const sidebarContent = (
    <>
      <div className="sidebar-section" aria-label="Threads" style={{ marginTop: 8 }}>
        <div
          className="sidebar-section-label"
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "0 16px",
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--color-text-secondary)",
            letterSpacing: "0.04em",
            textTransform: "uppercase",
            marginBottom: 8,
          }}
        >
          <span>
            Threads
            {threads.length > 0 ? (
              <span style={{ marginLeft: 8, textTransform: "none", opacity: 0.8 }}>
                · {threads.length} thread{threads.length === 1 ? "" : "s"}
              </span>
            ) : null}
          </span>
          <button
            type="button"
            onClick={handleNewThread}
            disabled={busy || listLoading}
            title="New thread"
            style={{
              background: "transparent",
              border: "1px solid var(--color-accent-cyan)",
              color: "var(--color-accent-cyan)",
              padding: "2px 8px",
              fontSize: 11,
              cursor: "pointer",
              borderRadius: 0,
            }}
          >+ NEW</button>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          {listLoading ? (
            <div style={{ padding: 16, color: "var(--color-text-secondary)", fontSize: 12 }}>
              Loading…
            </div>
          ) : threads.length === 0 ? (
            <div style={{ padding: 16, color: "var(--color-text-secondary)", fontSize: 12 }}>
              No threads yet. Click + NEW.
            </div>
          ) : (
            threads.map((t) => {
              const active = t.thread_id === selectedId;
              return (
                <button
                  key={t.thread_id}
                  type="button"
                  onClick={() => selectThread(t.thread_id)}
                  aria-label={`Open thread ${displayTitle(t)}`}
                  style={{
                    background: active ? "rgba(0, 240, 255, 0.06)" : "transparent",
                    border: "none",
                    borderLeft: active
                      ? "2px solid var(--color-accent-cyan)"
                      : "2px solid transparent",
                    color: "var(--color-text-primary)",
                    fontFamily: "var(--font-sans)",
                    fontSize: 13,
                    textAlign: "left",
                    padding: "8px 16px",
                    cursor: "pointer",
                  }}
                >
                  <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {displayTitle(t)}
                  </div>
                  {t.summary ? (
                    <div
                      data-testid="thread-list-summary"
                      style={{
                        fontSize: 11,
                        color: "var(--color-text-secondary)",
                        marginTop: 2,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                      }}
                    >
                      {t.summary}
                    </div>
                  ) : null}
                  <div style={{ fontSize: 10, color: "var(--color-text-secondary)", marginTop: 2, fontFamily: "var(--font-mono)" }}>
                    {t.message_count} msg · {relativeTime(t.updated_at)}
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>

      <div style={{
        marginTop: "auto",
        padding: 10,
        borderTop: "1px solid rgba(255,255,255,0.15)",
        display: "flex",
        justifyContent: "flex-end",
      }}>
        <button
          type="button"
          onClick={signOut}
          title="Clear the local session"
          style={{
            background: "transparent",
            border: "1px solid var(--color-text-secondary)",
            color: "var(--color-text-secondary)",
            padding: "4px 10px",
            fontSize: 11,
            cursor: "pointer",
            borderRadius: 0,
          }}
        >Sign out</button>
      </div>
    </>
  );

  const centerContent = !selectedId ? (
    <div style={{
      flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
      color: "var(--color-text-secondary)", fontSize: 14,
      padding: 24, textAlign: "center",
    }}>
      Pick a thread on the left, or click + NEW to start a new one.
    </div>
  ) : threadLoading && !activeMeta ? (
    <div style={{
      flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
      color: "var(--color-text-secondary)", fontSize: 14,
    }}>
      Loading thread…
    </div>
  ) : !activeMeta ? (
    <div style={{
      flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
      color: "var(--color-text-secondary)", fontSize: 14,
    }}>
      Thread not found.
    </div>
  ) : (
    <>
      <header style={{
        padding: "12px 16px",
        borderBottom: "1px solid rgba(255,255,255,0.15)",
      }}>
        <h2 style={{ margin: 0, fontSize: 16, color: "var(--color-text-primary)" }}>
          {displayTitle(activeMeta)}
        </h2>
        <div style={{ fontSize: 11, color: "var(--color-text-secondary)", marginTop: 4, fontFamily: "var(--font-mono)" }}>
          {activeMeta.message_count} message{activeMeta.message_count === 1 ? "" : "s"} · updated {relativeTime(activeMeta.updated_at)}
        </div>
      </header>

      {error ? (
        <div style={{
          background: "rgba(224, 32, 32, 0.1)",
          border: "1px solid var(--color-accent-red)",
          color: "var(--color-text-primary)",
          padding: 8,
          fontSize: 12,
          margin: "8px 16px",
        }}>
          {error}
        </div>
      ) : null}

      {/* Message log */}
      <div style={{
        flex: 1,
        overflowY: "auto",
        padding: "12px 16px",
      }}>
        {messages.length === 0 ? (
          <div style={{ color: "var(--color-text-secondary)", fontSize: 13, padding: 12 }}>
            No messages yet — say something below to start.
          </div>
        ) : (
          messages.map((m, idx) => (
            <Bubble key={`${m.ts_ms}-${idx}`} message={m} />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Composer */}
      <div style={{
        borderTop: "1px solid rgba(255,255,255,0.15)",
        padding: 12,
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}>
        <textarea
          value={composer}
          onChange={(e) => setComposer(e.target.value)}
          onKeyDown={onComposerKeyDown}
          placeholder="Type a message — Cmd/Ctrl+Enter to send"
          disabled={sending}
          aria-label="Compose message"
          rows={3}
          style={{
            background: "var(--color-bg-surface-alt)",
            color: "var(--color-text-primary)",
            fontFamily: "var(--font-sans)",
            fontSize: 14,
            border: "1px solid var(--color-text-secondary)",
            borderRadius: 4,
            padding: 10,
            outline: "none",
            resize: "vertical",
          }}
        />
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--color-text-secondary)" }}>
            {composer.length} char{composer.length === 1 ? "" : "s"}
          </span>
          <button
            type="button"
            onClick={handleSend}
            disabled={sending || !composer.trim()}
            style={{
              background: "transparent",
              border: "1px solid var(--color-accent-cyan)",
              color: "var(--color-accent-cyan)",
              padding: "6px 14px",
              fontSize: 12,
              cursor: sending || !composer.trim() ? "not-allowed" : "pointer",
              opacity: sending || !composer.trim() ? 0.5 : 1,
              borderRadius: 0,
              fontFamily: "var(--font-sans)",
              letterSpacing: "0.04em",
            }}
          >
            {sending ? "Sending…" : "SEND"}
          </button>
        </div>
      </div>
    </>
  );

  // Stable runOn payload for the ELINS / Physics tabs. We only pass
  // it when there's text to analyse, so the view shows its empty state
  // (with no Re-run button) on an empty thread instead of firing a
  // backend request against the empty string.
  const insightsRunOn = threadText
    ? { rawText: threadText, region: null }
    : null;

  const insightsContent = !activeMeta ? (
    <div style={{ padding: 16, fontSize: 12, color: "var(--color-text-secondary)" }}>
      No thread selected.
    </div>
  ) : (
    <>
      {/* v54-followup — InsightsPanel tab strip. THREAD is the legacy
          meta + summary + actions surface; ELINS and PHYSICS mount the
          v1 ELINS v2 and Emotional Physics views against the active
          thread's composed transcript. Mirrors desktop ChatWindow. */}
      <div
        role="tablist"
        aria-label="Insights view selector"
        data-testid="insights-tabs"
        style={{
          display: "flex",
          gap: 4,
          borderBottom: "1px solid rgba(255,255,255,0.10)",
          paddingBottom: 4,
          marginBottom: 4,
        }}
      >
        {(["thread", "elins", "physics"] as const).map((tab) => {
          const active = insightsTab === tab;
          const label =
            tab === "thread" ? "Thread"
            : tab === "elins"  ? "ELINS"
            :                    "Physics";
          return (
            <button
              key={tab}
              type="button"
              role="tab"
              aria-selected={active}
              data-testid={`insights-tab-${tab}`}
              onClick={() => setInsightsTab(tab)}
              style={{
                flex: 1,
                padding: "4px 6px",
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                background: "transparent",
                border: "1px solid",
                borderColor: active
                  ? "var(--color-accent-cyan)"
                  : "rgba(255,255,255,0.10)",
                color: active
                  ? "var(--color-accent-cyan)"
                  : "var(--color-text-secondary)",
                cursor: "pointer",
                borderRadius: 3,
              }}
            >
              {label}
            </button>
          );
        })}
      </div>

      {insightsTab === "thread" ? (
        <>
          <div style={{
            fontFamily: "var(--font-mono)",
            fontSize: 12,
            color: "var(--color-text-secondary)",
            lineHeight: 1.6,
          }}>
            <div>messages: {activeMeta.message_count}</div>
            <div>updated: {relativeTime(activeMeta.updated_at)}</div>
            {activeMeta.summary_ts_ms ? (
              <div>summary: {relativeTime(activeMeta.summary_ts_ms)}</div>
            ) : null}
          </div>

          {renaming ? (
            <div style={{
              padding: 8,
              background: "var(--color-bg-surface)",
              border: "1px solid var(--color-text-secondary)",
            }}>
              <div style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                color: "var(--color-text-secondary)",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                marginBottom: 4,
              }}>
                Rename thread
              </div>
              <input
                type="text"
                value={renameDraft}
                onChange={(e) => setRenameDraft(e.target.value)}
                autoFocus
                aria-label="Thread title"
                style={{
                  width: "100%",
                  background: "var(--color-bg-surface-alt)",
                  color: "var(--color-text-primary)",
                  border: "1px solid var(--color-text-secondary)",
                  padding: 6,
                  fontSize: 12,
                  fontFamily: "var(--font-sans)",
                }}
              />
              <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                <button
                  type="button"
                  onClick={commitRename}
                  disabled={busy}
                  style={insightsBtnPrimary}
                >{busy ? "Saving…" : "SAVE"}</button>
                <button
                  type="button"
                  onClick={cancelRename}
                  disabled={busy}
                  style={insightsBtn}
                >CANCEL</button>
              </div>
            </div>
          ) : activeMeta.summary ? (
            <div
              data-testid="thread-summary-card"
              style={{
                padding: 10,
                border: "1px solid rgba(255,255,255,0.15)",
                background: "var(--color-bg-surface)",
              }}
            >
              <div style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                color: "var(--color-text-secondary)",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                marginBottom: 4,
              }}>
                Summary
              </div>
              <div style={{
                fontSize: 13,
                color: "var(--color-text-primary)",
                lineHeight: 1.5,
              }}>
                {activeMeta.summary}
              </div>
            </div>
          ) : (
            <div style={{
              padding: 12,
              fontSize: 12,
              color: "var(--color-text-secondary)",
            }}>
              No summary yet.
            </div>
          )}

          {!renaming ? (
            <div style={{
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}>
              <button
                type="button"
                onClick={handleSummarize}
                disabled={busy}
                style={insightsBtn}
              >{busy ? "…" : "SUMMARIZE"}</button>
              <button
                type="button"
                onClick={startRename}
                disabled={busy}
                style={insightsBtn}
              >RENAME</button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={busy}
                style={insightsBtnDanger}
              >DELETE</button>
            </div>
          ) : null}
        </>
      ) : insightsTab === "elins" ? (
        insightsRunOn ? (
          <ElinsV2View
            envelope={threadElinsEnv}
            runOn={insightsRunOn}
            onRun={setThreadElinsEnv}
          />
        ) : (
          <div
            style={{ padding: 12, fontSize: 12, color: "var(--color-text-secondary)" }}
            data-testid="insights-elins-empty"
          >
            No messages yet — add a turn to run ELINS on this thread.
          </div>
        )
      ) : (
        insightsRunOn ? (
          <EmotionalPhysicsView
            response={threadEpRes}
            text={insightsRunOn.rawText}
            onAnalyze={setThreadEpRes}
          />
        ) : (
          <div
            style={{ padding: 12, fontSize: 12, color: "var(--color-text-secondary)" }}
            data-testid="insights-physics-empty"
          >
            No messages yet — add a turn to analyse this thread.
          </div>
        )
      )}
    </>
  );

  return (
    <WebShell
      userName={auth.user}
      onNavigate={onNavigate}
      activeNav="Threads"
      sidebar={sidebarContent}
      center={centerContent}
      insights={insightsContent}
    />
  );
}

// ---------------- Sub-components ----------------
function Bubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";
  const wrapperStyle: React.CSSProperties = {
    display: "flex",
    flexDirection: "column",
    alignItems: isUser ? "flex-end" : "flex-start",
    margin: "8px 0",
  };
  const bubbleStyle: React.CSSProperties = {
    maxWidth: "75%",
    padding: "8px 12px",
    background: "var(--color-bg-surface)",
    color: "var(--color-text-primary)",
    borderLeft: isAssistant ? "2px solid var(--color-accent-cyan)" : "none",
    borderRight: isUser ? "2px solid var(--color-accent-red)" : "none",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    fontSize: 14,
    lineHeight: 1.5,
  };
  return (
    <div style={wrapperStyle} data-role={message.role}>
      <div style={bubbleStyle}>{message.content}</div>
      {isAssistant && (message.model || message.grounding_status) ? (
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 2 }}>
          {message.model ? (
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                color: "var(--color-text-secondary)",
              }}
              data-testid="assistant-model"
            >
              {message.model}
            </span>
          ) : null}
          {/* A19 — #cite grounding badge (read-only, this-turn only) */}
          <GroundingBadge status={message.grounding_status} />
        </div>
      ) : null}
    </div>
  );
}

// A19 — small read-only badge surfacing the #cite grounding outcome.
// Renders nothing for non-#cite turns (null/undefined). Colors follow the
// A19 card: OK → #2ECC71, Incomplete → #E74C3C. (A18 emits only these two
// states; there is no distinct "retried" status to show.)
function GroundingBadge({ status }: { status?: GroundingStatus | null }) {
  if (status !== "grounded" && status !== "incomplete") return null;
  const ok = status === "grounded";
  const color = ok ? "#2ECC71" : "#E74C3C";
  const label = ok ? "Grounding: OK" : "Grounding: Incomplete";
  const tip = ok
    ? "Output passed grounding validation."
    : "Grounding failed after retry cap.";
  return (
    <span
      data-testid="grounding-badge"
      data-grounding={status}
      title={tip}
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: 10,
        color,
        border: `1px solid ${color}`,
        borderRadius: 3,
        padding: "0 6px",
        lineHeight: "16px",
        letterSpacing: "0.04em",
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </span>
  );
}

// ---------------- Inline button styles ----------------
const insightsBtn: React.CSSProperties = {
  background: "transparent",
  border: "1px solid var(--color-text-secondary)",
  color: "var(--color-text-primary)",
  padding: "6px 10px",
  fontSize: 12,
  cursor: "pointer",
  borderRadius: 0,
  fontFamily: "var(--font-sans)",
  letterSpacing: "0.04em",
};

const insightsBtnPrimary: React.CSSProperties = {
  ...insightsBtn,
  border: "1px solid var(--color-accent-cyan)",
  color: "var(--color-accent-cyan)",
};

const insightsBtnDanger: React.CSSProperties = {
  ...insightsBtn,
  border: "1px solid var(--color-accent-red)",
  color: "var(--color-accent-red)",
};

// ---------------- Helpers ----------------
function displayTitle(t: ThreadMeta): string {
  const raw = (t.title || "").trim();
  return raw || "Untitled Thread";
}

function relativeTime(ts_ms: number): string {
  if (!ts_ms) return "—";
  const diff = Date.now() - ts_ms;
  if (diff < 0) return new Date(ts_ms).toLocaleTimeString();
  const s = Math.floor(diff / 1000);
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d ago`;
  return new Date(ts_ms).toLocaleDateString();
}
