import styles from "./ChatSurface.module.css";
import AssistantMessage from "../AssistantMessage/AssistantMessage";
import UserMessage from "../UserMessage/UserMessage";

export default function ChatSurface() {
  return (
    <div className={styles.surface}>
      <AssistantMessage />
      <UserMessage />
    </div>
  );
}
