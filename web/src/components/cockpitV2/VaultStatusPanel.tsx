/**
 * VaultStatusPanel — wraps the existing components/cockpit/VaultStatus
 * (a props-driven component) and feeds it the ContinuitySnapshot held in
 * the vault slice.
 */
import { useCockpit } from "../../state/cockpitStore";
import VaultStatus from "../cockpit/VaultStatus";

export default function VaultStatusPanel() {
  const vault = useCockpit((s) => s.vault);

  return (
    <section className="cv2-panel">
      <header className="cv2-panel-head">Vault</header>
      <div className="cv2-panel-body">
        {vault.status === "loading" && <p className="cv2-muted">Loading…</p>}
        {vault.status === "error" && <p className="cv2-err">{vault.error}</p>}
        {(vault.status === "ready" || vault.snapshot) && (
          <VaultStatus snapshot={vault.snapshot} />
        )}
      </div>
    </section>
  );
}
