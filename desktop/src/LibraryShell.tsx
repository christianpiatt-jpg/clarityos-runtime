// ClarityOS desktop — Library shell.
//
// Renders inside the v1 ClarityOSSurface via DesktopShell. Hosts the
// LibraryView (browse-only over /library/list) in the CenterColumn.
//
// Mirrors PersonalElinsShell's layout discipline:
//   * sidebar holds only a Sign-out cap (rest comes from the v1
//     OperatorSidebar's NavItems)
//   * insights={null} so the v1 grid drops to two columns
//   * activeNav="Library" keeps the v1 NavItem highlighted

import { clearSession, getUser } from "./lib/api";
import DesktopShell from "./DesktopShell";
import LibraryView from "./components/v1/LibraryView/LibraryView";

interface Props {
  onSignOut: () => void;
  onNavigate: (label: string) => void;
}

export default function LibraryShell({ onSignOut, onNavigate }: Props) {
  const userName = getUser();

  const handleSignOut = () => {
    clearSession();
    onSignOut();
  };

  return (
    <DesktopShell
      userName={userName}
      onNavigate={onNavigate}
      activeNav="Library"
      sidebar={
        <div style={{
          marginTop: "auto",
          padding: 10,
          borderTop: "1px solid rgba(255,255,255,0.15)",
          display: "flex",
          justifyContent: "flex-end",
        }}>
          <button
            type="button"
            onClick={handleSignOut}
            title="Clear the local session"
            style={{
              background: "transparent",
              border: "1px solid var(--color-text-secondary)",
              color: "var(--color-text-secondary)",
              padding: "4px 10px",
              fontSize: 11,
              cursor: "pointer",
              borderRadius: 0,
            }}
          >Sign out</button>
        </div>
      }
      center={
        <div
          data-testid="library-shell-center"
          style={{
            flex: 1,
            overflowY: "auto",
            padding: 24,
            display: "flex",
            flexDirection: "column",
            gap: 20,
            minWidth: 0,
          }}
        >
          <LibraryView />
        </div>
      }
      insights={null}
    />
  );
}
