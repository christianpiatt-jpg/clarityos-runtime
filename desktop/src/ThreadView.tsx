// ClarityOS desktop — message log. Auto-scrolls to the bottom every
// time the messages array changes so the latest turn is in view after
// a send.

import { useEffect, useRef } from "react";
import type { ThreadMessage } from "./lib/api";

interface Props {
  messages: ThreadMessage[];
}

export default function ThreadView({ messages }: Props) {
  const endRef = useRef<HTMLDivElement | null>(null);

  // Defer the scroll one tick so the DOM has the new bubbles.
  useEffect(() => {
    const id = window.setTimeout(() => {
      endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
    }, 0);
    return () => window.clearTimeout(id);
  }, [messages.length]);

  return (
    <div className="log selectable">
      {messages.length === 0 ? (
        <div className="empty">No messages yet — say something below to start.</div>
      ) : (
        messages.map((m, idx) => (
          <Bubble key={`${m.ts_ms}-${idx}`} message={m} />
        ))
      )}
      <div ref={endRef} />
    </div>
  );
}

function Bubble({ message }: { message: ThreadMessage }) {
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";
  const cls =
    "bubble-row " + (isUser ? "user" : isAssistant ? "assistant" : "assistant");
  return (
    <div className={cls} data-role={message.role}>
      <div className="bubble">{message.content}</div>
      {isAssistant && message.model ? (
        <div className="bubble-model" data-testid="assistant-model">
          {message.model}
        </div>
      ) : null}
    </div>
  );
}
