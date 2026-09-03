/**
 * SendToCorpus — the "send to corpus" control in the ElinsV2View footer.
 *
 * A diagnostic run is transient: the input text is analysed and discarded.
 * This posts that same input text (runOn.rawText) through the corpus front
 * door (/ingest/manual), so the run the member just read can be KEPT in the
 * library with an object_vector -- the same door as the cockpit box, with a
 * different `source` so the two entrances stay tellable apart in the store.
 *
 * Self-contained: owns its own request state so the view's run state is
 * untouched. The parent mounts it with key={text}, so this instance's
 * "sent" belongs to exactly one text; a new transcript is a fresh instance.
 * After a success the button is DISABLED: the server mints a new id per
 * call, so a second press would be a duplicate row, not a confirmation.
 *
 * The envelope already on screen is NOT re-sent -- the server re-runs ELINS
 * on the stored text and keeps its own envelope; the binding has no field
 * for a caller-supplied one.
 */
import { useState } from "react";
import { Link } from "react-router-dom";

import { ingestManual } from "../../../lib/api";
import styles from "./ElinsV2View.module.css";

export default function SendToCorpus({
  text, region,
}: {
  text: string;
  region: string | null;
}) {
  const [busy, setBusy] = useState(false);
  const [sentId, setSentId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canSend = !busy && !sentId && text.trim().length > 0;

  async function send() {
    if (!canSend) return;
    setBusy(true);
    setError(null);
    try {
      const r = await ingestManual({ text, region, source: "elins_v2_view" });
      setSentId(r.library_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        className={styles.actionBtn}
        data-testid="send-to-corpus"
        onClick={send}
        disabled={!canSend}
        aria-label="Send this run's input text to the corpus"
        title={`Stores this run's input text (${text.length} characters) in your library`}
      >
        {busy ? "sending…" : sentId ? "sent to corpus" : "send to corpus"}
      </button>
      {sentId ? (
        <span className={styles.railNote} data-testid="send-to-corpus-result">
          {sentId} · <Link to="/library">open library</Link>
        </span>
      ) : null}
      {error ? (
        // The view's own error style, not a muted note: a failed post is a
        // failure, and reads as one.
        <span className={styles.error} data-testid="send-to-corpus-error">{error}</span>
      ) : null}
    </>
  );
}
