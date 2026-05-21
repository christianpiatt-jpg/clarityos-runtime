// AuthToggle.tsx — v74 / Unit 84.
//
// Resolved per agent-mesh decision: NOT a mode switcher. Static
// informational block displaying FOUNDING500_ACCESS (what the
// membership unlocks). Naming retained from Gemini's component
// tree.

import styles from "./Unit84.module.css";

const ACCESS_HEADER = "Access Scope";
const ACCESS_ITEMS: ReadonlyArray<string> = [
  "Early cockpit entry",
  "Operator Timeline",
  "Org Timeline, founder-gated",
  "EL/INS indicators",
  "Rollup views",
  "Subscription portal",
  "Priority beta support",
];

export default function AuthToggle() {
  return (
    <section
      className={styles.authToggle}
      aria-label="Access scope"
      data-testid="auth-toggle"
    >
      <h3>{ACCESS_HEADER}</h3>
      <ul className={styles.authToggleList}>
        {ACCESS_ITEMS.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}
