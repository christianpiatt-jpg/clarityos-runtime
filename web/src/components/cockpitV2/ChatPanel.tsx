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

  const { status, messages, meta, error } = thread;

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

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
        {status === "error" && <p className="cv2-err">{error}</p>}
        {status !== "loading" &&
          messages.map((m, i) => {
            // Mirrors Threads.tsx:823-825 — the model footer and the badges
            // share one row, and the row is skipped entirely when there is
            // nothing to put in it.
            const isAssistant = m.role === "assistant";
            const showRow = isAssistant && (Boolean(m.model) || hasDirectiveSurface(m));
            return (
              <div key={`${m.ts_ms}-${i}`} className={"cv2-msg cv2-msg-" + m.role}>
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
        {status === "ready" && messages.length === 0 && (
          <p className="cv2-muted">No messages yet.</p>
        )}
      </div>

      <form className="cv2-composer" onSubmit={onSend}>
        <input
          className="cv2-input"
          value={input}
          placeholder="Message…"
          disabled={composerDisabled}
          onChange={(e) => setInput(e.target.value)}
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
