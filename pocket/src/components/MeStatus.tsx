import { useEffect, useState } from "react";

import { me, isAuthenticated, AuthRequiredError, type MeResponse } from "../api/client";
import { isOperator, isVaultReady } from "../lib/role";

/**
 * MeStatus — small header chip-row showing the current account's
 * operator badge + vault readiness dot.
 *
 * Behavior:
 *   * If unauthenticated locally (no session id in localStorage)
 *     -> render NOTHING. We do not poke ``/me`` because that would
 *     trigger the centralized 401 redirect on any public route
 *     (e.g. ``/landing``).
 *   * If authenticated -> fetch ``/me``, render an OPERATOR pill
 *     when ``me.operator``, and a green/yellow vault dot per
 *     ``me.vault_ready``.
 *   * On any error (network, AuthRequiredError, etc.) -> render
 *     nothing rather than show a broken state in the header.
 *
 * Mount-once: this component fetches /me on initial render only.
 * Header state doesn't need to be reactive to backend changes
 * mid-session — the per-screen /me calls (on /me, /runs, etc.)
 * keep the rest of the surface in sync.
 */
export default function MeStatus() {
  const [data, setData] = useState<MeResponse | null>(null);

  useEffect(() => {
    if (!isAuthenticated()) {
      setData(null);
      return;
    }
    let cancelled = false;
    me()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        // Silent failure in the header. AuthRequiredError is the
        // expected outcome when the session is expired; apiFetch's
        // centralized handler will already have done the redirect.
        if (!cancelled && !(e instanceof AuthRequiredError)) {
          /* swallow; header stays empty */
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!data) return null;

  const op = isOperator(data);
  const ready = isVaultReady(data);

  return (
    <div className="pkt-me-status" role="status" aria-live="polite">
      {op ? (
        <span
          className="pkt-badge pkt-badge--operator"
          title="Operator privileges active"
        >
          OPERATOR
        </span>
      ) : null}
      <span
        className={`pkt-vault-dot ${
          ready ? "pkt-vault-dot--ready" : "pkt-vault-dot--degraded"
        }`}
        title={ready ? "Vault Ready" : "Vault Degraded"}
        aria-label={ready ? "Vault Ready" : "Vault Degraded"}
      />
    </div>
  );
}
