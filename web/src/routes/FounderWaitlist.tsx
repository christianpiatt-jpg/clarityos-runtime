// routes/FounderWaitlist.tsx — founder-only waitlist console.
//
// Stub Founder Console host (the spec says "from v33 or stub if not yet
// present"). For now this is a single-page surface that mounts
// WaitlistPanel; later passes can compose more panels around it.

import WaitlistPanel from "../components/founder/WaitlistPanel";

export default function FounderWaitlist() {
  return (
    <div className="founder-console" style={{ maxWidth: 900, margin: "0 auto" }}>
      <h1 style={{ marginTop: 0 }}>Founder console — Waitlist</h1>
      <p style={{ color: "#666", fontSize: 13, marginTop: -8 }}>
        Public waitlist signups. Founder-only.
      </p>
      <WaitlistPanel />
    </div>
  );
}
