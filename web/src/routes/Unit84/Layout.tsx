// Layout.tsx — v74 / Unit 84.
//
// Top-level layout wrapper for the Unit 84 surface. Owns the full
// viewport (bypasses the cockpit's default Layout) so the Somatic
// canvas + 1px red boundary read clean. Mounted as the route
// element at /founding500/confirm.
//
// Files-per-spec budget: 6 total. Layout doubles as the route
// entry to keep us at 6 without a 7th orchestrator file.

import GlobalHeader from "./GlobalHeader";
import SubscriptionGate from "./SubscriptionGate";
import styles from "./Unit84.module.css";

export default function Layout() {
  return (
    <div className={styles.canvas} data-testid="unit84-canvas">
      <GlobalHeader />
      <main className={styles.main} data-testid="unit84-main">
        <SubscriptionGate />
      </main>
    </div>
  );
}
