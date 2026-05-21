// components/founder/FounderDashboard.tsx — composed Founder view.
//
// Composes CohortList + waitlist + DM + member tools + ELINS + #cmt
// into a single page. The /founder route mounts this component.

import { useState } from "react";
import { Link } from "react-router-dom";
import CohortList from "./CohortList";
import WaitlistPanel from "./WaitlistPanel";
import MemberDetailPanel from "./MemberDetailPanel";
import ManualActivateButton from "./ManualActivateButton";
import DMNotesPanel from "./DMNotesPanel";
import ELINSInspector from "./ELINSInspector";
import CommentGeneratorPanel from "./CommentGeneratorPanel";
import ForecastPanel from "./forecast/ForecastPanel";
import RegionalPanel from "./regional/RegionalPanel";
import MacroPanel from "./macro/MacroPanel";
import EntityGraphPanel from "./entities/EntityGraphPanel";
import FounderBillingPanel from "./billing/FounderBillingPanel";
import FounderAnalyticsSummary from "./analytics/FounderAnalyticsSummary";
import FounderModelStatusPanel from "./models/FounderModelStatusPanel";
import FounderVaultInspector from "./vault/FounderVaultInspector";

export default function FounderDashboard() {
  const [selectedUser, setSelectedUser] = useState<string>("");

  return (
    <div className="founder-dashboard" style={{ maxWidth: 960, margin: "0 auto" }}>
      <h1 style={{ marginTop: 0 }}>Founder console</h1>
      <p style={{ color: "#666", fontSize: 13, marginTop: -8, marginBottom: 8 }}>
        Cohort + waitlist + DMs + ELINS QC + #cmt. Founder-only.
      </p>
      <p style={{ marginTop: 0, marginBottom: 16, fontSize: 12 }}>
        <Link to="/dashboard" style={{ color: "var(--os-focus, #00F0FF)", textDecoration: "none" }}>
          → Open ELINS dashboard
        </Link>
      </p>

      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: 16,
        alignItems: "start",
      }}>
        <CohortList />
        <MemberDetailPanel selected={selectedUser} onSelect={setSelectedUser} />

        <ManualActivateButton user={selectedUser} />
        <DMNotesPanel scopeUser={selectedUser || undefined} />

        <div style={{ gridColumn: "1 / span 2" }}>
          <WaitlistPanel />
        </div>

        <ELINSInspector />
        <CommentGeneratorPanel />

        <div style={{ gridColumn: "1 / span 2" }}>
          <ForecastPanel title="Forecast engine (v34) — example" />
        </div>

        <div style={{ gridColumn: "1 / span 2" }}>
          <RegionalPanel />
        </div>

        <div style={{ gridColumn: "1 / span 2" }}>
          <MacroPanel />
        </div>

        <div style={{ gridColumn: "1 / span 2" }}>
          <EntityGraphPanel />
        </div>

        <div style={{ gridColumn: "1 / span 2" }}>
          <FounderBillingPanel />
        </div>

        <div style={{ gridColumn: "1 / span 2" }}>
          <FounderAnalyticsSummary />
        </div>

        <div style={{ gridColumn: "1 / span 2" }}>
          <FounderModelStatusPanel />
        </div>

        <div style={{ gridColumn: "1 / span 2" }}>
          <FounderVaultInspector />
        </div>
      </div>
    </div>
  );
}
