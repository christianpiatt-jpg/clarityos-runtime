import { useState } from "react";
import styles from "./ClarityOSSurface.module.css";
import TopBar from "../TopBar/TopBar";
import OperatorSidebar from "../OperatorSidebar/OperatorSidebar";
import CenterColumn from "../CenterColumn/CenterColumn";
import InsightsPanel from "../InsightsPanel/InsightsPanel";

export default function ClarityOSSurface() {
  // Sole piece of state in the v1 surface — InsightsPanel collapse.
  const [insightsOpen, setInsightsOpen] = useState<boolean>(true);
  const gridClass = insightsOpen
    ? styles.mainGrid
    : `${styles.mainGrid} ${styles.mainGridCollapsed}`;
  return (
    <div className={styles.root}>
      <TopBar />
      <div className={gridClass}>
        <OperatorSidebar />
        <CenterColumn />
        <InsightsPanel
          open={insightsOpen}
          onToggle={() => setInsightsOpen((v) => !v)}
        />
      </div>
    </div>
  );
}
