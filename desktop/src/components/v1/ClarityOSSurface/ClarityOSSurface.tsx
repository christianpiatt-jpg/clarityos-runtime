// Surface v1 root — MODIFIED for desktop integration.
//
// Accepts optional slot props for each pane so callers can inject
// real-data content while preserving the locked v1 geometry. When a
// slot is omitted, the original harness default renders (for parity
// with the verified harness behaviour).

import { useState } from "react";
import type { ReactNode } from "react";
import styles from "./ClarityOSSurface.module.css";
import TopBar from "../TopBar/TopBar";
import OperatorSidebar from "../OperatorSidebar/OperatorSidebar";
import CenterColumn from "../CenterColumn/CenterColumn";
import InsightsPanel from "../InsightsPanel/InsightsPanel";

interface ClarityOSSurfaceProps {
  topBar?: ReactNode;
  sidebar?: ReactNode;
  center?: ReactNode;
  insights?: ReactNode;
  /** Controlled-mode collapse state. When provided, parent owns. */
  insightsOpen?: boolean;
  onInsightsToggle?: () => void;
}

export default function ClarityOSSurface({
  topBar,
  sidebar,
  center,
  insights,
  insightsOpen: insightsOpenProp,
  onInsightsToggle,
}: ClarityOSSurfaceProps = {}) {
  const [internalOpen, setInternalOpen] = useState<boolean>(true);
  const open = insightsOpenProp ?? internalOpen;
  const toggle = onInsightsToggle ?? (() => setInternalOpen((v) => !v));
  // ``insights === null`` means "no insights panel at all" — grid drops
  // to two columns. Distinct from ``insights === undefined`` (default
  // InsightsPanel) and ``insights === <X />`` (custom content).
  const noInsights = insights === null;
  const gridClass = noInsights
    ? `${styles.mainGrid} ${styles.mainGridNoInsights}`
    : open
    ? styles.mainGrid
    : `${styles.mainGrid} ${styles.mainGridCollapsed}`;
  return (
    <div className={styles.root}>
      {topBar ?? <TopBar />}
      <div className={gridClass}>
        {sidebar ?? <OperatorSidebar />}
        {center ?? <CenterColumn />}
        {noInsights
          ? null
          : insights ?? <InsightsPanel open={open} onToggle={toggle} />}
      </div>
    </div>
  );
}
