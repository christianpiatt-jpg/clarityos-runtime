import styles from "./InputActions.module.css";
import ActionIcon from "../ActionIcon/ActionIcon";

export default function InputActions() {
  return (
    <div className={styles.actions}>
      <ActionIcon kind="attach" />
      <ActionIcon kind="expand" />
      <ActionIcon kind="send" />
    </div>
  );
}
