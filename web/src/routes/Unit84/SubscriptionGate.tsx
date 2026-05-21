// SubscriptionGate.tsx — v74 / Unit 84.
//
// Gate state machine + parent orchestrator. Renders:
//   * BETA_NOTICE (default state, above the children)
//   * children: Founding500Badge + AuthToggle + ActionControl
//   * SUCCESS (post-confirm state, replaces the entire gate)
//
// Both BETA_NOTICE and SUCCESS are conditional render-regions —
// NOT separate files (per Perplexity mapping rule).
//
// On confirm success, navigates to /cockpit after a short delay
// so the user can read the SUCCESS copy before being redirected.

import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Founding500Badge from "./Founding500Badge";
import AuthToggle from "./AuthToggle";
import ActionControl, { type ActionControlErrorCode } from "./ActionControl";
import styles from "./Unit84.module.css";

const BETA_NOTICE_HEADER = "Founding 500 Beta";
const BETA_NOTICE_BODY_1 = "ClarityOS is in beta.";
const BETA_NOTICE_BODY_2 =
  "Founding 500 operators receive early access to the active environment.";

const SUCCESS_HEADER = "Access Confirmed";
const SUCCESS_BODY_1 = "Founding 500 status is active.";
const SUCCESS_BODY_2 = "Operator entry is now available.";

const ERROR_MESSAGES: Record<ActionControlErrorCode, string> = {
  subscription_inactive:
    "No active subscription detected. If you just completed checkout, wait a moment and refresh.",
  cohort_full:
    "The Founding 500 cohort is at capacity. Contact support if you completed payment.",
  generic: "Confirmation failed. Try again, or contact support if the issue persists.",
};

const REDIRECT_DELAY_MS = 1000;
const REDIRECT_TARGET = "/cockpit";

type Status = "idle" | "submitting" | "success" | "error";

export interface SubscriptionGateProps {
  /** Optional override — used by tests to avoid real navigation. */
  onConfirmSuccess?: () => void;
  /** Optional override — used by tests to inspect error code. */
  onConfirmError?: (code: ActionControlErrorCode) => void;
}

export default function SubscriptionGate({
  onConfirmSuccess,
  onConfirmError,
}: SubscriptionGateProps = {}) {
  const navigate = useNavigate();
  const [status, setStatus] = useState<Status>("idle");
  const [errorCode, setErrorCode] = useState<ActionControlErrorCode | null>(null);
  const redirectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (redirectTimer.current !== null) {
        clearTimeout(redirectTimer.current);
      }
    };
  }, []);

  function handleSuccess() {
    setStatus("success");
    setErrorCode(null);
    if (onConfirmSuccess) {
      onConfirmSuccess();
      return;
    }
    redirectTimer.current = setTimeout(() => {
      navigate(REDIRECT_TARGET);
    }, REDIRECT_DELAY_MS);
  }

  function handleError(code: ActionControlErrorCode) {
    setStatus("error");
    setErrorCode(code);
    onConfirmError?.(code);
  }

  if (status === "success") {
    return (
      <section
        className={styles.gate}
        data-testid="subscription-gate-success"
        aria-live="polite"
      >
        <div className={styles.gateSuccess}>
          <h2>{SUCCESS_HEADER}</h2>
          <p>{SUCCESS_BODY_1}</p>
          <p>{SUCCESS_BODY_2}</p>
        </div>
      </section>
    );
  }

  return (
    <section
      className={styles.gate}
      data-testid="subscription-gate"
      aria-label="Founding 500 subscription gate"
    >
      <div className={styles.gateNotice} data-testid="subscription-gate-notice">
        <h2>{BETA_NOTICE_HEADER}</h2>
        <p>{BETA_NOTICE_BODY_1}</p>
        <p>{BETA_NOTICE_BODY_2}</p>
      </div>

      <Founding500Badge />
      <AuthToggle />
      <ActionControl onSuccess={handleSuccess} onError={handleError} />

      {status === "error" && errorCode !== null && (
        <div
          className={styles.gateError}
          role="alert"
          data-testid="subscription-gate-error"
        >
          {ERROR_MESSAGES[errorCode]}
        </div>
      )}
    </section>
  );
}
