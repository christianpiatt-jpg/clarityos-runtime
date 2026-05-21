// ClarityOS desktop — composer. Cmd/Ctrl+Enter sends; plain Enter
// inserts a newline so multi-line prompts compose naturally. Mirrors
// web v48's Threads.tsx composer behaviour.

import { useCallback, useState } from "react";

interface Props {
  onSend: (content: string) => Promise<void> | void;
  disabled: boolean;
  sending: boolean;
}

export default function Composer({ onSend, disabled, sending }: Props) {
  const [draft, setDraft] = useState("");

  const send = useCallback(async () => {
    const trimmed = draft.trim();
    if (!trimmed || disabled) return;
    await onSend(trimmed);
    setDraft("");
  }, [draft, disabled, onSend]);

  return (
    <div className="composer">
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
            e.preventDefault();
            void send();
          }
        }}
        placeholder="Type a message — Cmd/Ctrl+Enter to send"
        disabled={sending}
        className="selectable"
        aria-label="Compose message"
      />
      <button
        type="button"
        className="btn btn-primary"
        onClick={() => void send()}
        disabled={disabled || draft.trim().length === 0}
      >{sending ? "…" : "Send"}</button>
    </div>
  );
}
