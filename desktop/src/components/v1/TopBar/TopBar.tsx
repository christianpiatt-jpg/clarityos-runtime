import styles from "./TopBar.module.css";
import SystemStatusIndicator from "../SystemStatusIndicator/SystemStatusIndicator";
import ModelSelector from "../ModelSelector/ModelSelector";
import UserIdentityChip from "../UserIdentityChip/UserIdentityChip";

export default function TopBar() {
  return (
    <header className={styles.topBar}>
      <SystemStatusIndicator />
      <ModelSelector />
      <UserIdentityChip />
    </header>
  );
}
