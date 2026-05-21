import styles from "./InsightsPanel.module.css";
import InsightsHeader from "../InsightsHeader/InsightsHeader";
import JsonBlock from "../JsonBlock/JsonBlock";
import ElinsGridBlock from "../ElinsGridBlock/ElinsGridBlock";
import ElinsRunList from "../ElinsRunList/ElinsRunList";

export default function InsightsPanel({
  open,
  onToggle,
}: {
  open: boolean;
  onToggle: () => void;
}) {
  const panelClass = open
    ? styles.panel
    : `${styles.panel} ${styles.panelCollapsed}`;
  return (
    <aside className={panelClass}>
      <InsightsHeader open={open} onToggle={onToggle} />
      {open ? (
        <div className={styles.body}>
          <JsonBlock />
          <ElinsGridBlock />
          <ElinsRunList />
        </div>
      ) : null}
    </aside>
  );
}
