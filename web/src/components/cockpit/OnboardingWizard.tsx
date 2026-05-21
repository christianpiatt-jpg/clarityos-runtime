// components/cockpit/OnboardingWizard.tsx — first-run checklist.
//
// Shows three checkpoints (vault, Dewey, snapshot) and posts to
// /v29/onboarding/complete as the user clicks each one. Hidden once
// /v29/onboarding/state reports `done: true`.

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  v29OnboardingComplete,
  v29OnboardingSeed,
  v29OnboardingState,
  type V29OnboardingState,
} from "../../lib/api";
import { useFlags } from "../../hooks/useFlags";
import { useMembership } from "../../hooks/useMembership";

interface Step {
  id: "vault_check" | "dewey_sync" | "continuity_snapshot";
  title: string;
  description: string;
}

const STEPS: Step[] = [
  {
    id: "vault_check",
    title: "1. Confirm vault is reachable",
    description: "Loads /vault/list to verify your storage layer is connected.",
  },
  {
    id: "dewey_sync",
    title: "2. Sync Dewey neighborhoods",
    description: "Fetches your Dewey metadata so #G has neighborhoods to consult.",
  },
  {
    id: "continuity_snapshot",
    title: "3. Take a continuity snapshot",
    description: "Captures cross-session metadata so the cockpit has something to render.",
  },
];

export default function OnboardingWizard() {
  const [state, setState] = useState<V29OnboardingState | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [seedSummary, setSeedSummary] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const s = await v29OnboardingState();
      setState(s);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const completeStep = useCallback(async (id: Step["id"]) => {
    setBusy(id);
    setError(null);
    try {
      await v29OnboardingComplete(id);
      await refresh();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setBusy(null);
    }
  }, [refresh]);

  const seedDemo = useCallback(async () => {
    setBusy("seed");
    setError(null);
    try {
      const r = await v29OnboardingSeed();
      const s = r.summary;
      setSeedSummary(
        s.skipped
          ? "Vault already has items — nothing seeded."
          : `Seeded ${s.vault} vault items, ${s.timeline} timeline events.`,
      );
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setBusy(null);
    }
  }, []);

  if (state === null) {
    return <div style={{ color: "#999", fontSize: 12 }}>Checking onboarding…</div>;
  }
  if (state.done) {
    return <PostOnboardingMembershipOffer />;
  }

  const completed = new Set(state.completed);

  return (
    <section style={{
      border: "1px solid #d6d6e6",
      background: "#f6f6ff",
      borderRadius: 6,
      padding: 12,
      marginBottom: 16,
    }}>
      <h2 style={{ margin: "0 0 6px 0", fontSize: 14 }}>First-run checklist</h2>
      <p style={{ margin: 0, fontSize: 12, color: "#445" }}>
        Tap each step once you've verified it works. Optional — you can use the
        cockpit without finishing this list.
      </p>
      <ol style={{ marginTop: 12, paddingLeft: 18 }}>
        {STEPS.map((step) => {
          const done = completed.has(step.id);
          return (
            <li key={step.id} style={{ marginBottom: 8 }}>
              <strong>{step.title}</strong>
              <div style={{ color: "#556", fontSize: 12 }}>{step.description}</div>
              {done ? (
                <span style={{ color: "#147" }}>✓ done</span>
              ) : (
                <button
                  onClick={() => void completeStep(step.id)}
                  disabled={busy !== null}
                  style={{ marginTop: 4 }}
                >
                  {busy === step.id ? "Working…" : "Mark done"}
                </button>
              )}
            </li>
          );
        })}
      </ol>
      <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid #ddd" }}>
        <button onClick={() => void seedDemo()} disabled={busy !== null}>
          {busy === "seed" ? "Seeding…" : "Seed demo data (optional)"}
        </button>
        {seedSummary && (
          <div style={{ marginTop: 6, fontSize: 12, color: "#445" }}>
            {seedSummary}
          </div>
        )}
      </div>
      {error && (
        <div style={{
          marginTop: 8,
          padding: 6,
          background: "#fee",
          border: "1px solid #f99",
          fontSize: 12,
        }}>
          {error}
        </div>
      )}
    </section>
  );
}

/**
 * Post-onboarding membership offer.
 *
 * Rendered once `/v29/onboarding/state.done` flips true. Shows the
 * Founding-cohort offer if:
 *   - membership_ui_enabled flag is on, AND
 *   - founder_tier_enabled flag is on, AND
 *   - the user is not already an active member.
 *
 * Two paths:
 *   - "Activate" → navigate to /membership (let the user accept terms there).
 *   - "Decline / not now" → dismiss the card; limited mode (no #G runs).
 *
 * Dismiss state lives in localStorage so the card doesn't re-appear on
 * every cockpit visit.
 */
function PostOnboardingMembershipOffer() {
  const { flags } = useFlags();
  const { state } = useMembership();
  const [dismissed, setDismissed] = useState(() => {
    try { return localStorage.getItem("clarityos.membership_offer_dismissed") === "1"; }
    catch { return false; }
  });

  if (dismissed) return null;
  if (flags.membership_ui_enabled !== true) return null;
  if (flags.founder_tier_enabled !== true) return null;
  if (state?.membership.status === "active") return null;

  const dismiss = () => {
    try { localStorage.setItem("clarityos.membership_offer_dismissed", "1"); } catch {}
    setDismissed(true);
  };

  const cohortFull = state?.cohort.is_full;
  const nextPrice = state?.membership.next_price ?? 50;

  return (
    <section style={{
      border: "1px solid #d6d6e6",
      background: "#fafaff",
      borderRadius: 6,
      padding: 12,
      marginBottom: 16,
    }}>
      <h2 style={{ margin: "0 0 6px 0", fontSize: 14 }}>
        {cohortFull ? "Join the waitlist" : "Founding 500 — locked at $50"}
      </h2>
      <p style={{ margin: 0, fontSize: 12, color: "#445" }}>
        {cohortFull
          ? "The Founding 500 cohort is full. You can join the waitlist; if a spot opens you'll be charged the locked price."
          : `Member price: $${nextPrice.toFixed(2)} (locked for life of membership). Without membership, #G runs and #c features are unavailable.`}
      </p>
      <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
        <Link to="/membership">
          <button style={{ fontWeight: 600 }}>
            {cohortFull ? "Join waitlist →" : "Activate →"}
          </button>
        </Link>
        <button onClick={dismiss}>Not now</button>
      </div>
    </section>
  );
}
