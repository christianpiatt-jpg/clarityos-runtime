import styles from "./InsightsHeader.module.css";

export default function InsightsHeader({
  open,
  onToggle,
}: {
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <div className={styles.header}>
      <span className={styles.title}>&gt;INSIGHTS</span>
      <button
        type="button"
        className={styles.handle}
        onClick={onToggle}
        aria-label={open ? "collapse insights" : "expand insights"}
      />
    </div>
  );
}
