import styles from "./ModelSelector.module.css";

const MODELS = ["claude", "gpt", "gemini", "grok", "local"] as const;
const ACTIVE: (typeof MODELS)[number] = "claude";

export default function ModelSelector() {
  return (
    <div className={styles.selector} role="tablist">
      {MODELS.map((m) => {
        const cls =
          m === ACTIVE
            ? `${styles.button} ${styles.buttonActive}`
            : styles.button;
        return (
          <button key={m} type="button" role="tab" className={cls}>
            {m}
          </button>
        );
      })}
    </div>
  );
}
