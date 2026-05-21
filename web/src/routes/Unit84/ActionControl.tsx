// ActionControl.tsx — v74 / Unit 84.
//
// Consent + action. Receives TERMS + CHECKBOX + CONSIDERATION +
// ACTION as frozen narrative consts. Checkbox gates the button:
// disabled until accepted && !submitting.
//
// On click POSTs to /membership/confirm via confirmMembership()
// and propagates outcome via onSuccess / onError props.

import { useState } from "react";
import { ApiError, confirmMembership } from "../../lib/api";
import styles from "./Unit84.module.css";

const TERMS_HEADER = "Beta Access Terms";
const TERMS_BODY: ReadonlyArray<string> = [
  "Beta access requires agreement before entry.",
  "Features may change before public release.",
  "Core primitives remain fixed.",
];

const CHECKBOX_LABEL =
  "I have read and agree to the Beta Terms and Privacy Policy, and I " +
  "acknowledge that ClarityOS beta features may change, contain defects, " +
  "or be discontinued before public release.";

const CONSIDERATION_HEADER = "Founding Terms";
const CONSIDERATION_BODY_1 =
  "Founding members assist in development during the beta phase.";
const CONSIDERATION_BODY_2 =
  "In consideration, they receive fixed lifetime pricing and Founder's Circle membership.";

const ACTION_LABEL = "Confirm Founding 500 Membership";

export type ActionControlErrorCode =
  | "subscription_inactive"
  | "cohort_full"
  | "generic";

export interface ActionControlProps {
  onSuccess: () => void;
  onError: (code: ActionControlErrorCode) => void;
}

function classifyError(err: unknown): ActionControlErrorCode {
  if (err instanceof ApiError) {
    if (err.code === "subscription_inactive") return "subscription_inactive";
    if (err.code === "cohort_full") return "cohort_full";
  }
  return "generic";
}

export default function ActionControl({ onSuccess, onError }: ActionControlProps) {
  const [accepted, setAccepted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const disabled = !accepted || submitting;

  async function handleClick() {
    if (disabled) return;
    setSubmitting(true);
    try {
      await confirmMembership();
      onSuccess();
    } catch (err) {
      onError(classifyError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section
      className={styles.action}
      aria-label="Confirm Founding 500 membership"
      data-testid="action-control"
    >
      <div className={styles.actionSection}>
        <h4>{TERMS_HEADER}</h4>
        {TERMS_BODY.map((line) => (
          <p key={line}>{line}</p>
        ))}
      </div>

      <label className={styles.consent}>
        <input
          type="checkbox"
          checked={accepted}
          onChange={(e) => setAccepted(e.target.checked)}
          data-testid="action-control-checkbox"
          aria-label="Accept beta terms and privacy policy"
        />
        <span>{CHECKBOX_LABEL}</span>
      </label>

      <div className={styles.actionSection}>
        <h4>{CONSIDERATION_HEADER}</h4>
        <p>{CONSIDERATION_BODY_1}</p>
        <p>{CONSIDERATION_BODY_2}</p>
      </div>

      <button
        type="button"
        className={styles.button}
        disabled={disabled}
        onClick={handleClick}
        data-testid="action-control-submit"
      >
        {submitting ? "CONFIRMING…" : ACTION_LABEL}
      </button>
    </section>
  );
}
