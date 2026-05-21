import styles from "./CenterColumn.module.css";
import ChatSurface from "../ChatSurface/ChatSurface";
import InputBar from "../InputBar/InputBar";

export default function CenterColumn() {
  return (
    <section className={styles.column}>
      <ChatSurface />
      <InputBar />
    </section>
  );
}
