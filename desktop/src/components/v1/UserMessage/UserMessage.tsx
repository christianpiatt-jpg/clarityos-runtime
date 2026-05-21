import styles from "./UserMessage.module.css";

export default function UserMessage() {
  return (
    <article className={styles.message}>
      <div className={styles.body} />
      <div className={styles.timestamp}>--:--:--</div>
    </article>
  );
}
