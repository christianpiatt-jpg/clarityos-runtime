/**
 * EnvelopeViewerPanel — shows the envelope for the currently selected
 * session (GET /markov/envelope/latest, held in the envelope slice).
 * Deterministic key/value render of the MarkovEnvelopeLatest shape.
 */
import { useCockpit, type SessionEnvelope } from "../../state/cockpitStore";

function fmt(v: number): string {
  return Number.isFinite(v) ? v.toFixed(4) : String(v);
}

function EnvelopeFields({ data }: { data: SessionEnvelope }) {
  const qc = data.qc_envelope ?? {};
  const metrics = data.envelope_metrics ?? {};
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
      {Object.entries(qc).map(([k, v]) => (
        <div className="cv2-kv-row" key={"qc-" + k}>
          <dt>{k}</dt>
          <dd className="cv2-mono">{fmt(v)}</dd>
        </div>
      ))}
      {Object.entries(metrics).map(([k, v]) => (
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
