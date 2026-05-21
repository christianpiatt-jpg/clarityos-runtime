/**
 * ChatPanel — minimal real chat for CockpitV2.
 *
 * The existing components/v1/ChatSurface is a static stub (no props, no data),
 * so it cannot be wrapped. This panel is a small, deterministic chat surface
 * built on the existing threads API (lib/api: listThreads / createThread /
 * getThread / postThreadMessage). No streaming, single thread — per spec.
 */
import { useEffect, useRef, useState, type FormEvent } from "react";

import { listThreads, createThread, getThread, postThreadMessage } from "../../lib/api";

type ThreadDetail = Awaited<ReturnType<typeof getThread>>;
type ChatMessage = ThreadDetail["messages"][number];
type Phase = "loading" | "ready" | "sending" | "error";

export default function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  // One-shot guard for the init effect below (StrictMode double-invoke).
  const createdRef = useRef(false);

  useEffect(() => {
    // React StrictMode double-invokes mount effects in dev. Without this
    // guard, both runs race on listThreads()/createThread() — each sees an
    // empty thread list before the other's createThread lands — and two
    // "Cockpit" threads get created. The ref persists across StrictMode's
    // simulated remount, so the init runs exactly once.
    if (createdRef.current) return;
    createdRef.current = true;
    (async () => {
      try {
        const threads = await listThreads();
        const meta = threads[0] ?? (await createThread("Cockpit"));
        const detail = await getThread(meta.thread_id);
        setThreadId(detail.meta.thread_id);
        setMessages(detail.messages);
        setPhase("ready");
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed to load chat");
        setPhase("error");
      }
    })();
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  async function onSend(e: FormEvent): Promise<void> {
    e.preventDefault();
    const text = input.trim();
    if (!text || !threadId || phase === "sending") return;
    setPhase("sending");
    setInput("");
    try {
      const res = await postThreadMessage(threadId, text);
      setMessages((prev) => [...prev, res.user_message, res.assistant_message]);
      setPhase("ready");
    } catch (e) {
      setError(e instanceof Error ? e.message : "send failed");
      setPhase("error");
    }
  }

  const composerDisabled = phase === "loading" || !threadId;

  return (
    <section className="cv2-panel cv2-chat">
      <header className="cv2-panel-head">Chat</header>

      <div className="cv2-chat-scroll" ref={scrollRef}>
        {phase === "loading" && <p className="cv2-muted">Loading…</p>}
        {phase === "error" && <p className="cv2-err">{error}</p>}
        {phase !== "loading" &&
          messages.map((m, i) => (
            <div key={`${m.ts_ms}-${i}`} className={"cv2-msg cv2-msg-" + m.role}>
              <span className="cv2-msg-role">{m.role}</span>
              <p className="cv2-msg-body">{m.content}</p>
            </div>
          ))}
        {phase === "ready" && messages.length === 0 && (
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
          disabled={phase === "sending" || composerDisabled || !input.trim()}
        >
          {phase === "sending" ? "Sending…" : "Send"}
        </button>
      </form>
    </section>
  );
}
