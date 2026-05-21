// v1 insights panel — MODIFIED to accept children rendered in place
// of the default body (JsonBlock + ElinsGridBlock + ElinsRunList) so
// the desktop can inject thread-aware insights (summary, meta, actions).
import type { ReactNode } from "react";
import styles from "./InsightsPanel.module.css";
import InsightsHeader from "../InsightsHeader/InsightsHeader";
import JsonBlock from "../JsonBlock/JsonBlock";
import ElinsGridBlock from "../ElinsGridBlock/ElinsGridBlock";
import ElinsRunList from "../ElinsRunList/ElinsRunList";

interface Props {
  open: boolean;
  onToggle: () => void;
  children?: ReactNode;
}

export default function InsightsPanel({ open, onToggle, children }: Props) {
  const panelClass = open
    ? styles.panel
    : `${styles.panel} ${styles.panelCollapsed}`;
  return (
    <aside className={panelClass}>
      <InsightsHeader open={open} onToggle={onToggle} />
      {open ? (
        <div className={styles.body}>
          {children ?? (
            <>
              <JsonBlock />
              <ElinsGridBlock />
              <ElinsRunList />
            </>
          )}
        </div>
      ) : null}
    </aside>
  );
}
