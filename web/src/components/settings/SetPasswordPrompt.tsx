// One-time, dismissible offer to set a password (pen ruling 2026-08-12).
//
// Shown on the magic-link landing surface, once, and never forced. Dismissal
// is remembered locally; setting a password also marks it seen so it does not
// reappear.
//
// LIMITATION, stated rather than hidden: /me does not expose `auth_method`, so
// this cannot ask the server whether a password already exists. It is gated on
// local storage only — clearing site data would surface the offer once more to
// a member who already set one. Making it state-aware needs `auth_method` on
// /me, which was outside this change's scope.
import { useState } from "react";
import { Link } from "react-router-dom";

export const PW_PROMPT_KEY = "clarityos_pw_prompt_seen";

export function markPasswordPromptSeen() {
  try {
    localStorage.setItem(PW_PROMPT_KEY, "1");
  } catch {
    /* storage unavailable — the prompt simply shows again */
  }
}

function alreadySeen(): boolean {
  try {
    return localStorage.getItem(PW_PROMPT_KEY) === "1";
  } catch {
    return false;
  }
}

export default function SetPasswordPrompt() {
  const [hidden, setHidden] = useState(alreadySeen);
  if (hidden) return null;

  function dismiss() {
    markPasswordPromptSeen();
    setHidden(true);
  }

  return (
    <div className="panel" style={{ marginBottom: 16 }}>
      <p className="muted" style={{ margin: 0, fontSize: "0.85rem" }}>
        You are signed in with an emailed link. If you would rather not wait on
        your inbox next time, you can{" "}
        <Link to="/membership" onClick={dismiss}>set a password</Link>. Optional —
        the link keeps working either way.
      </p>
      <button
        className="btn"
        style={{ marginTop: 10 }}
        onClick={dismiss}
      >
        NOT NOW
      </button>
    </div>
  );
}
