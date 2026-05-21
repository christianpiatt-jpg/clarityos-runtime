// ClarityOS desktop — Surface 3 / Strategy B / B1-thread-below-nav.
//
// Thin slot adapter that wraps the v1 ClarityOSSurface with real-data
// content fed in via children. The desktop's ChatWindow constructs
// the per-pane content; this file is responsible only for the v1
// shell composition + insights collapse state.

import { useState } from "react";
import type { ReactNode } from "react";
import ClarityOSSurface from "./components/v1/ClarityOSSurface/ClarityOSSurface";
import topBarStyles from "./components/v1/TopBar/TopBar.module.css";
import SystemStatusIndicator from "./components/v1/SystemStatusIndicator/SystemStatusIndicator";
import ModelSelector from "./components/v1/ModelSelector/ModelSelector";
import UserIdentityChip from "./components/v1/UserIdentityChip/UserIdentityChip";
import OperatorSidebar from "./components/v1/OperatorSidebar/OperatorSidebar";
import CenterColumn from "./components/v1/CenterColumn/CenterColumn";
import InsightsPanel from "./components/v1/InsightsPanel/InsightsPanel";

interface Props {
  /** Display name for the top-right user chip. */
  userName?: string | null;
  /** Content rendered below the static NavItems in the sidebar. */
  sidebar: ReactNode;
  /** Content rendered inside the center column. */
  center: ReactNode;
  /** Content rendered inside the insights panel body (when open).
   *  Pass ``null`` to render NO insights pane at all (2-col grid). */
  insights: ReactNode;
  /** NavItem click handler. */
  onNavigate?: (label: string) => void;
  /** Currently active nav-item label (for highlighting). */
  activeNav?: string;
}

export default function DesktopShell({
  userName, sidebar, center, insights, onNavigate, activeNav,
}: Props) {
  const [insightsOpen, setInsightsOpen] = useState<boolean>(true);
  const toggle = () => setInsightsOpen((v) => !v);
  const noInsights = insights === null;

  return (
    <ClarityOSSurface
      insightsOpen={insightsOpen}
      onInsightsToggle={toggle}
      topBar={
        <header className={topBarStyles.topBar}>
          <SystemStatusIndicator />
          <ModelSelector />
          <UserIdentityChip name={userName ?? undefined} />
        </header>
      }
      sidebar={
        <OperatorSidebar onNavigate={onNavigate} activeNav={activeNav}>
          {sidebar}
        </OperatorSidebar>
      }
      center={<CenterColumn>{center}</CenterColumn>}
      insights={
        noInsights ? null : (
          <InsightsPanel open={insightsOpen} onToggle={toggle}>
            {insights}
          </InsightsPanel>
        )
      }
    />
  );
}
