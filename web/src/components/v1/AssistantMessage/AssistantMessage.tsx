import styles from "./AssistantMessage.module.css";

export default function AssistantMessage() {
  return (
    <article className={styles.message}>
      <div className={styles.modelIndicator}>anthropic / claude-3.7</div>
      <div className={styles.body} />
      <div className={styles.timestamp}>--:--:--</div>
    </article>
  );
}
