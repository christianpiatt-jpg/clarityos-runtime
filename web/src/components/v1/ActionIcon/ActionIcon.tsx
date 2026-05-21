import styles from "./ActionIcon.module.css";

export type ActionIconKind = "attach" | "expand" | "send";

export default function ActionIcon({ kind }: { kind: ActionIconKind }) {
  return (
    <button
      type="button"
      className={styles.icon}
      aria-label={kind}
      data-kind={kind}
    />
  );
}
