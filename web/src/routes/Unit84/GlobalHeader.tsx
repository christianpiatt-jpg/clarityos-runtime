// GlobalHeader.tsx — v74 / Unit 84.
//
// Second layout file per Gemini's tree:
//   GlobalHeader
//    ├─ LogoBlock
//    └─ StatusIndicator
//
// No narrative; structure only. The ClarityOS mark sits on the
// left, a small mono status line ("FOUNDING 500 GATE · UNIT 84")
// on the right. 1px red bottom border from CSS module.

import styles from "./Unit84.module.css";

export default function GlobalHeader() {
  return (
    <header
      className={styles.header}
      role="banner"
      data-testid="unit84-global-header"
    >
      <div className={styles.headerLogo} data-testid="unit84-logo">
        ClarityOS
      </div>
      <div className={styles.headerStatus} data-testid="unit84-status">
        FOUNDING 500 GATE · UNIT 84
      </div>
    </header>
  );
}
