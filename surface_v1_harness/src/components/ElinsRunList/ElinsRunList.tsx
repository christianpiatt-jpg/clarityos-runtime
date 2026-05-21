import styles from "./ElinsRunList.module.css";

const PLACEHOLDER_RUNS = ["node_01", "node_02", "node_03", "node_04"] as const;

export default function ElinsRunList() {
  return (
    <ul className={styles.list} aria-label="ELINS run list">
      {PLACEHOLDER_RUNS.map((id) => (
        <li key={id} className={styles.entry}>
          {id}
        </li>
      ))}
    </ul>
  );
}
