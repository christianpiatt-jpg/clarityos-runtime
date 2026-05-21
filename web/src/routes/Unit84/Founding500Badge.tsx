// Founding500Badge.tsx — v74 / Unit 84.
//
// Atomic. Receives FOUNDING500_BADGE narrative as a const.
// Visual contract (Somatic): 1px cyan border, uppercase mono,
// pulse-opacity 1.0 -> 0.7 @ 0.5Hz, cyan-sphere glow.
//
// Per the mesh authority hierarchy:
//   Narrative -> Perplexity (frozen below as `const`s)
//   Structure -> Gemini (one inline-flex pill)
//   Implementation -> Claude (this file)

import styles from "./Unit84.module.css";

const BADGE_HEADER = "Founding 500";
const BADGE_BODY_1 = "Fixed lifetime pricing.";
const BADGE_BODY_2 = "Founder's Circle membership.";

export default function Founding500Badge() {
  return (
    <div
      className={styles.badge}
      role="status"
      aria-label="Founding 500 membership badge"
      data-testid="founding500-badge"
    >
      <span className={styles.badgeHeader}>{BADGE_HEADER}</span>
      <span className={styles.badgeBody}>
        {BADGE_BODY_1} {BADGE_BODY_2}
      </span>
    </div>
  );
}
