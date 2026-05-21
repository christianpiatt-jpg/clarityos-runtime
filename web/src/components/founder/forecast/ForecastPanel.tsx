// components/founder/forecast/ForecastPanel.tsx
//
// Composite panel that renders the v34 forecast block. Two modes:
//   1. ``block`` prop given → render directly (used by the ELINS inspector
//      after a /elins/preview run, since the canonical pipeline now
//      embeds ``forecast_engine``).
//   2. No prop → fetch /elins/forecast/example so the panel works as a
//      standalone surface on first paint.

import { useCallback, useEffect, useState } from "react";
import { elinsForecastExample, type V34ForecastBlock } from "../../../lib/api";
import PrimitiveEnvelopeChart from "./PrimitiveEnvelopeChart";
import MultiEnvelopeChart from "./MultiEnvelopeChart";
import DomainEnvelopeChart from "./DomainEnvelopeChart";
import ChainEnvelopeChart from "./ChainEnvelopeChart";

export interface ForecastPanelProps {
  block?: V34ForecastBlock | null;
  title?: string;
  compact?: boolean;
}

export default function ForecastPanel({
  block: providedBlock, title = "ELINS forecast", compact = false,
}: ForecastPanelProps) {
  const [block, setBlock] = useState<V34ForecastBlock | null>(providedBlock || null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<string | null>(null);

  useEffect(() => {
    setBlock(providedBlock || null);
  }, [providedBlock]);

  const loadExample = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await elinsForecastExample();
      setBlock(r.example.forecast);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    if (!providedBlock && !block && !loading) {
      void loadExample();
    }
    // run-once when the panel mounts without a provided block
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <section style={panelStyle}>
      <header style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 8 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>{title}</h2>
        {block && (
          <span style={{ fontSize: 11, color: "var(--os-text-tertiary, #585858)", fontFamily: "var(--font-mono, monospace)" }}>
            {block.version} · D+0..D+{block.days}
          </span>
        )}
      </header>

      {error && <div style={errorStyle}>{error}</div>}
      {loading && !block && <div style={{ fontSize: 12, color: "var(--os-text-secondary)" }}>Loading example…</div>}

      {block && (
        <div style={{ display: "grid", gap: compact ? 8 : 16 }}>
          <Section title="Multi-primitive envelope">
            <MultiEnvelopeChart values={block.multi_envelope} />
          </Section>

          <Section
            title="Per-primitive envelopes"
            help="Hover a primitive name to highlight its curve"
          >
            <PrimitiveEnvelopeChart envelopes={block.primitive_envelopes} highlight={highlight} />
            <div style={{ marginTop: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
              {Object.keys(block.primitive_envelopes).map((k) => (
                <button
                  key={k}
                  type="button"
                  onMouseEnter={() => setHighlight(k)}
                  onMouseLeave={() => setHighlight(null)}
                  onFocus={() => setHighlight(k)}
                  onBlur={() => setHighlight(null)}
                  style={{
                    fontSize: 11, padding: "2px 8px", border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
                    borderRadius: "var(--radius-pill, 999px)", background: highlight === k ? "var(--os-elevated, #1a1a1a)" : "var(--os-surface, #111)",
                    color: "var(--os-text-primary, #fff)", cursor: "pointer",
                  }}
                >
                  {k}
                </button>
              ))}
            </div>
          </Section>

          <Section title="Domain envelopes">
            <DomainEnvelopeChart domains={block.domain_envelopes} />
          </Section>

          <Section title="Causal-chain envelope">
            <ChainEnvelopeChart values={block.chain_envelope} chain={block.chain} />
          </Section>
        </div>
      )}
    </section>
  );
}

function Section({ title, help, children }: { title: string; help?: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 4 }}>
        <h3 style={{ fontSize: 12, margin: 0, color: "var(--os-text-secondary, #A0A0A0)", textTransform: "uppercase", letterSpacing: 0.5 }}>{title}</h3>
        {help && <span style={{ fontSize: 10, color: "var(--os-text-tertiary, #585858)" }}>{help}</span>}
      </div>
      {children}
    </div>
  );
}

const panelStyle: React.CSSProperties = {
  border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
  borderRadius: "var(--radius-md, 8px)",
  padding: 12,
  background: "var(--os-surface, #111)",
  color: "var(--os-text-primary, #fff)",
  marginBottom: 12,
};

const errorStyle: React.CSSProperties = {
  padding: 6,
  background: "rgba(224, 32, 32, 0.1)",
  border: "1px solid var(--os-boundary, #E02020)",
  borderRadius: "var(--radius-sm, 4px)",
  fontSize: 12,
  color: "#fca5a5",
  marginBottom: 8,
};
