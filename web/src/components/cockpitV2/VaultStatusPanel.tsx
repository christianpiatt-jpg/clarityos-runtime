/**
 * VaultStatusPanel — wraps components/cockpit/VaultStatus and feeds it the
 * ContinuitySnapshot held in the vault slice.
 *
 * #218 (CT-1 2026-09-09) -- THE LINK IS NEVER GATED. The body used to
 * render only once the snapshot was ready, which was right when the body
 * was twenty rows OF that snapshot. The body is now a static route link
 * that needs no data at all, so gating it meant a failed /continuity/
 * snapshot left the member looking at an error string with NO way to
 * reach their vault -- and at first paint (status "idle", which matched
 * no branch) at nothing whatever. The link renders always; the fetch's
 * own state is a quiet line beneath it, and only when it is not "ready".
 */
import { useCockpit } from "../../state/cockpitStore";
import VaultStatus from "../cockpit/VaultStatus";

export default function VaultStatusPanel() {
  const vault = useCockpit((s) => s.vault);

  return (
    <section className="cv2-panel">
      <header className="cv2-panel-head">Vault</header>
      <div className="cv2-panel-body">
        <VaultStatus snapshot={vault.snapshot} />
        {vault.status === "error" && (
          <p className="cv2-err" data-testid="vault-snapshot-error">
            counts unread: {vault.error}
          </p>
        )}
      </div>
    </section>
  );
}
