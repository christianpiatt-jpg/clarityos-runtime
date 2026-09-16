import styles from "./AssistantMessage.module.css";

/** #162 (f) on the web, #151 here -- the model indicator READS a model id;
 *  it never asserts one. The static "anthropic / claude-3.7" this replaced
 *  named a model the registry no longer carries. The v1 ChatSurface stub
 *  passes nothing, so it shows a dash. */
export default function AssistantMessage({ modelId }: { modelId?: string | null } = {}) {
  return (
    <article className={styles.message}>
      <div className={styles.modelIndicator} data-testid="model-indicator">
        {modelId ? `model: ${modelId}` : "model: —"}
      </div>
      <div className={styles.body} />
      <div className={styles.timestamp}>--:--:--</div>
    </article>
  );
}
