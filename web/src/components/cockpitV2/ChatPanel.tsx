/**
 * ChatPanel — minimal real chat for CockpitV2.
 *
 * The existing components/v1/ChatSurface is a static stub (no props, no data),
 * so it cannot be wrapped. This panel is a small, deterministic chat surface
 * built on the existing threads API. No streaming, single thread — per spec.
 *
 * v55 — the thread itself now lives in the cockpit store's `thread` slice so
 * ThreadInsightsPanel reads the same transcript and meta. This panel owns the
 * composer and the transcript render only.
 *
 * A19/A30 — each assistant turn carries the directive surface that rides on
 * the live POST response (grounding_status / directive_metadata). It is
 * attached in the store's send action and rendered here with the same shared
 * badges the /threads route uses.
 */
import { useEffect, useRef, type FormEvent, useState } from "react";

import { useCockpit, cockpit } from "../../state/cockpitStore";
import {
  DirectiveBadge,
  GroundingBadge,
  hasDirectiveSurface,
  nonCiteDirectives,
} from "../shared/DirectiveBadges";

export default function ChatPanel() {
  const thread = useCockpit((s) => s.thread);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  // The ring marks the answer that just arrived, then releases. It is
  // attention moving, not a permanent highlight -- so a new turn re-arms
  // it and the next keystroke drops it.
  const [ringReleased, setRingReleased] = useState(false);

  const { status, messages, meta, error, failedSend } = thread;

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  // A new turn landed -- re-arm.
  useEffect(() => { setRingReleased(false); }, [messages.length]);

  async function onSend(e: FormEvent): Promise<void> {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    setInput("");
    await cockpit.thread.actions.send(text);
  }

  const composerDisabled = status === "loading" || !meta;

  return (
    <section className="cv2-panel cv2-chat">
      <header className="cv2-panel-head">Chat</header>

      <div className="cv2-chat-scroll" ref={scrollRef}>
        {status === "loading" && <p className="cv2-muted">Loading…</p>}
        {/* ★ The bare banner used to be the ONLY failure signal, and it sat
            at the TOP of the pane, detached from the message it referred
            to -- which had already been erased from the composer. It is
            kept only for non-send failures (load, delete); a failed SEND
            renders inline below, attached to the words that did not go. */}
        {status === "error" && !failedSend && <p className="cv2-err">{error}</p>}
        {status !== "loading" &&
          messages.map((m, i) => {
            // Mirrors Threads.tsx:823-825 — the model footer and the badges
            // share one row, and the row is skipped entirely when there is
            // nothing to put in it.
            const isAssistant = m.role === "assistant";
            const isLatest =
              isAssistant && i === messages.length - 1 && !ringReleased;
            const showRow = isAssistant && (Boolean(m.model) || hasDirectiveSurface(m));
            return (
              <div
                key={`${m.ts_ms}-${i}`}
                className={"cv2-msg cv2-msg-" + m.role + (isLatest ? " is-latest" : "")}
              >
                <span className="cv2-msg-role">{m.role}</span>
                <p className="cv2-msg-body">{m.content}</p>
                {showRow ? (
                  <div className="cv2-msg-meta">
                    {m.model ? (
                      <span className="cv2-msg-model" data-testid="assistant-model">
                        {m.model}
                      </span>
                    ) : null}
                    {/* A19 — #cite grounding badge (read-only, this-turn only) */}
                    <GroundingBadge status={m.grounding_status} />
                    {/* A30 — unified badges for the other active directives */}
                    {nonCiteDirectives(m).map((name) => (
                      <DirectiveBadge
                        key={name}
                        name={name}
                        status={(m.directive_metadata?.[name]?.status as string | null) ?? null}
                      />
                    ))}
                  </div>
                ) : null}
              </div>
            );
          })}
        {/* ★★ THE FAILED SEND, RENDERED WHERE IT HAPPENED.
            Visually distinct from persisted history, carrying the member's
            actual text and the reason, with a retry. Before this a failed
            message simply vanished. */}
        {failedSend ? (
          <div className="cv2-msg cv2-msg-failed" data-testid="failed-send">
            <span className="cv2-msg-role">not sent</span>
            <p className="cv2-msg-body">{failedSend.text}</p>
            <div className="cv2-msg-meta">
              <span className="cv2-err" data-testid="failed-send-error">
                {failedSend.error}
              </span>
              <button
                type="button"
                className="cv2-btn"
                data-testid="failed-send-retry"
                onClick={() => {
                  const text = failedSend.text;
                  cockpit.thread.actions.clearFailedSend();
                  void cockpit.thread.actions.send(text);
                }}
              >
                Retry
              </button>
              <button
                type="button"
                className="cv2-btn"
                data-testid="failed-send-edit"
                onClick={() => {
                  setInput(failedSend.text);
                  cockpit.thread.actions.clearFailedSend();
                }}
              >
                Edit
              </button>
            </div>
          </div>
        ) : null}
        {status === "ready" && messages.length === 0 && !failedSend && (
          <p className="cv2-muted">No messages yet.</p>
        )}
      </div>

      <form
        className={"cv2-composer" + (status === "sending" ? " is-sending" : "")}
        onSubmit={onSend}
      >
        <input
          className="cv2-input"
          value={input}
          placeholder="Message…"
          disabled={composerDisabled}
          onChange={(e) => {
            setInput(e.target.value);
            setRingReleased(true);
          }}
        />
        <button
          className="cv2-btn cv2-btn-primary"
          type="submit"
          disabled={status === "sending" || composerDisabled || !input.trim()}
        >
          {status === "sending" ? "Sending…" : "Send"}
        </button>
      </form>
    </section>
  );
}
