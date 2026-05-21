// routes/Founder.tsx — composed Founder console.
//
// The API enforces the founder-cohort gate; this route is just the
// surface. /founder/waitlist remains as a deep-link shortcut into the
// waitlist panel for backwards compat.

import FounderDashboard from "../components/founder/FounderDashboard";

export default function Founder() {
  return <FounderDashboard />;
}
