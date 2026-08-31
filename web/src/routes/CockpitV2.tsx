/**
 * CockpitV2 — consolidated operator cockpit (route: /cockpit-v2).
 *
 * Additive surface. Self-gated: renders its own login panel when the
 * operator is not authenticated, the three-column cockpit when they are.
 * Bypasses Layout + RequireAuth so it owns the viewport. Touches no
 * existing route, component, or token file.
 *
 * Layout — CSS grid, fixed left/right columns, flexible center:
 *   left:   Session list · Engine selector · Vault status
 *   center: Chat
 *   right:  Thread insights · Envelope viewer · Runtime
 */
import { useEffect } from "react";

import { useCockpit, cockpit, bootstrapCockpit } from "../state/cockpitStore";
import CockpitLoginPanel from "../components/cockpitV2/CockpitLoginPanel";
import SessionListPanel from "../components/cockpitV2/SessionListPanel";
import ViewSelectorPanel from "../components/cockpitV2/ViewSelectorPanel";
import PersonalElinsComposerPanel from "../components/cockpitV2/PersonalElinsComposerPanel";
import PersonalElinsInsightsPanel from "../components/cockpitV2/PersonalElinsInsightsPanel";
import VaultStatusPanel from "../components/cockpitV2/VaultStatusPanel";
import ChatPanel from "../components/cockpitV2/ChatPanel";
import EnvelopeViewerPanel from "../components/cockpitV2/EnvelopeViewerPanel";
import RuntimePanel from "../components/cockpitV2/RuntimePanel";
import ThreadInsightsPanel from "../components/cockpitV2/ThreadInsightsPanel";
import "../styles/cockpitV2.css";

export default function CockpitV2() {
  const authStatus = useCockpit((s) => s.auth.status);
  const user = useCockpit((s) => s.auth.user);
  const view = useCockpit((s) => s.view);

  useEffect(() => {
    if (authStatus === "authed") bootstrapCockpit();
  }, [authStatus]);

  if (authStatus !== "authed") {
    return (
      <div className="cv2-shell cv2-shell-center">
        <CockpitLoginPanel />
      </div>
    );
  }

  return (
    <div className="cv2-shell">
      <header className="cv2-topbar">
        <span className="cv2-brand">ClarityOS · Cockpit</span>
        <span className="cv2-topbar-right">
          <span className="cv2-muted">{user}</span>
          <button
            type="button"
            className="cv2-btn"
            onClick={() => cockpit.auth.actions.logout()}
          >
            Sign out
          </button>
        </span>
      </header>

      <div className="cv2-grid">
        <aside className="cv2-col">
          <ViewSelectorPanel />
          <SessionListPanel />
          <VaultStatusPanel />
        </aside>

        {/* ★ Only the centre and right columns switch. The left column,
            the topbar and the grid are identical in both views. */}
        <main className="cv2-col cv2-col-center">
          {view === "personal" ? <PersonalElinsComposerPanel /> : <ChatPanel />}
        </main>

        <aside className="cv2-col">
          {view === "personal" ? (
            <PersonalElinsInsightsPanel />
          ) : (
            <>
              <ThreadInsightsPanel />
              <EnvelopeViewerPanel />
            </>
          )}
          <RuntimePanel />
        </aside>
      </div>
    </div>
  );
}
