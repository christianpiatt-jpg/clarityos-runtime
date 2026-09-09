/**
 * EnvelopeViewerPanel — shows the envelope for the currently selected
 * session (GET /markov/envelope/latest, held in the envelope slice).
 *
 * #203 (CT-1 2026-09-09) — THE PANEL RENDERS THE ROWS IT EARNS. It used
 * to print every key of qc_envelope and envelope_metrics. On the thread
 * path nobody computes those: _write_thread_markov_state copies the prior
 * envelope forward and starts from the IDENTITY one, so the panel showed
 * qc_predictive 1.0000 · qc_stability 1.0000 · qc_drift 0.0000 ·
 * qc_pressure 0.0000 and three 0.0000 trends — the same eight numbers on
 * every turn of every thread, forever. A constant rendered to four
 * decimals reads as a measurement. CT-1 measured it on screen 09-09.
 *
 * The backend still WRITES the field and the wire still carries it: this
 * is a render change, and the rows come back the day something computes
 * them on this path.
 *
 * "UNTIL SOMETHING COMPUTES THEM" IS THE RULE, not "never again". The
 * /markov/chat path DOES compute a real envelope (app.py: qc_stability
 * from a similarity, qc_drift from it, qc_predictive from an exponential,
 * qc_pressure from curvatures, and real trends) and writes it to the same
 * store this panel reads. So the test is not "which path" but "is this a
 * reading or the identity constant": a qc envelope that differs from the
 * identity one, or a trend that is not zero, IS a measurement and renders.
 */
import { useCockpit, type SessionEnvelope } from "../../state/cockpitStore";

/** app.py _IDENTITY_QC_ENVELOPE -- what the thread path copies forward
 *  forever. Matching it exactly means nobody has measured anything. */
const IDENTITY_QC: Record<string, number> = {
  qc_stability: 1.0,
  qc_drift: 0.0,
  qc_predictive: 1.0,
  qc_pressure: 0.0,
};

function fmt(v: number): string {
  return Number.isFinite(v) ? v.toFixed(4) : String(v);
}

/** A reading, not the constant: any key the identity envelope does not
 *  have, or any value that differs from it. */
export function qcIsMeasured(qc: Record<string, number> | undefined): boolean {
  const entries = Object.entries(qc ?? {});
  if (entries.length === 0) return false;
  return entries.some(([k, v]) => !(k in IDENTITY_QC) || v !== IDENTITY_QC[k]);
}

/** app.py _DEFAULT_ENVELOPE_METRICS is three zeros; a non-zero trend is a
 *  reading. */
export function metricsAreMeasured(m: Record<string, number> | undefined): boolean {
  const values = Object.values(m ?? {});
  return values.length > 0 && values.some((v) => v !== 0);
}

function EnvelopeFields({ data }: { data: SessionEnvelope }) {
  const stateIndex = typeof data.state_index === "number" ? data.state_index : null;
  const qc = data.qc_envelope;
  const metrics = data.envelope_metrics;
  return (
    <dl className="cv2-kv">
      <div className="cv2-kv-row">
        <dt>state vector</dt>
        <dd className="cv2-mono">{data.state_vector?.length ?? 0} dims</dd>
      </div>
      <div className="cv2-kv-row">
        <dt>predictive vector</dt>
        <dd className="cv2-mono">{data.predictive_vector?.length ?? 0} dims</dd>
      </div>
      <div className="cv2-kv-row">
        <dt>state index</dt>
        <dd className="cv2-mono">{stateIndex === null ? "\u2014" : stateIndex}</dd>
      </div>
      {qcIsMeasured(qc) &&
        Object.entries(qc!).map(([k, v]) => (
          <div className="cv2-kv-row" key={"qc-" + k}>
            <dt>{k}</dt>
            <dd className="cv2-mono">{fmt(v)}</dd>
          </div>
        ))}
      {metricsAreMeasured(metrics) &&
        Object.entries(metrics!).map(([k, v]) => (
          <div className="cv2-kv-row" key={"m-" + k}>
            <dt>{k}</dt>
            <dd className="cv2-mono">{fmt(v)}</dd>
          </div>
        ))}
    </dl>
  );
}

export default function EnvelopeViewerPanel() {
  const envelope = useCockpit((s) => s.envelope);
  const selectedId = useCockpit((s) => s.session.selectedId);

  return (
    <section className="cv2-panel">
      <header className="cv2-panel-head">Envelope</header>
      <div className="cv2-panel-body">
        {!selectedId && <p className="cv2-muted">Select a session.</p>}
        {selectedId && envelope.status === "loading" && <p className="cv2-muted">Loading…</p>}
        {selectedId && envelope.status === "error" && <p className="cv2-err">{envelope.error}</p>}
        {selectedId && envelope.status === "ready" && envelope.data && (
          <EnvelopeFields data={envelope.data} />
        )}
      </div>
    </section>
  );
}
