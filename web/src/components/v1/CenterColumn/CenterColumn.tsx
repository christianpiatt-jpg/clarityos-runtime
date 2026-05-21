// v1 center column — accepts children that replace the default
// ChatSurface + InputBar when the web client renders its own chat.
import type { ReactNode } from "react";
import styles from "./CenterColumn.module.css";
import ChatSurface from "../ChatSurface/ChatSurface";
import InputBar from "../InputBar/InputBar";

interface Props {
  children?: ReactNode;
}

export default function CenterColumn({ children }: Props = {}) {
  return (
    <section className={styles.column}>
      {children ?? (
        <>
          <ChatSurface />
          <InputBar />
        </>
      )}
    </section>
  );
}
