import styles from "./InputField.module.css";

export default function InputField() {
  return (
    <input
      type="text"
      className={styles.field}
      placeholder="Type a message"
      aria-label="message input"
    />
  );
}
