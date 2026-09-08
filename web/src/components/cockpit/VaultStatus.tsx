// components/cockpit/VaultStatus.tsx — Vault Status Indicator panel.
// Reads the continuity snapshot (already loaded by the cockpit) so the
// rail never pulls full vault items.
//
// #180b (2) -- THE VAULT RAIL RENDERS WHAT THE SNAPSHOT CARRIES. Eighteen
// keys arrived here and died: the five coherence flags, the eight per-store
// last_updated_ts stamps, the last episode and its stamp, and now_ts.
//   coherence_flags.*      -> five WORDS (ok / not ok), never a number
//   last_updated_ts.*      -> one "last updated" per store, in the title
//   memory_context.last_episode.{sentiment, weight} -> one line
//   C: snapshot.now_ts -- the server's clock at read time, not a fact
//      about the vault (#180b 2)
// A boolean false renders its word; a missing key renders "—".

import { Link } from "react-router-dom";
import type { ContinuitySnapshot } from "../../services/continuity";

export interface VaultStatusProps {
  snapshot: ContinuitySnapshot | null;
}

const DASH = "—";

/** The five flags, as the snapshot names them (identity · elins ·
 *  trajectory · cross_scale · universal). */
const FLAGS = ["identity_ok", "elins_ok", "trajectory_ok", "cross_scale_ok", "universal_ok"] as const;
/** The eight stores that carry a last_updated_ts. */
const STORES = [
  "envelope", "events_decay", "identity", "trajectory",
  "elins", "universal_physics", "coherence", "memory_context",
] as const;

function stamp(ts: unknown): string {
  if (typeof ts !== "number" || !Number.isFinite(ts) || ts <= 0) return DASH;
  return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 16) + "Z";
}
function flagWord(v: unknown): string {
  return v === true ? "ok" : v === false ? "not ok" : DASH;
}
function obj(v: unknown): Record<string, unknown> {
  return v !== null && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}
function shown(v: unknown): string {
  if (v === null || v === undefined) return DASH;
  if (typeof v === "number") return Number.isFinite(v) ? String(v) : DASH;
  if (typeof v === "boolean") return v ? "yes" : "no";
  return String(v) || DASH;
}

export default function VaultStatus({ snapshot }: VaultStatusProps) {
  const counts = snapshot?.counts ?? {};
  const entries = Object.entries(counts).sort();
  const flags = obj(snapshot?.coherence_flags);
  const lts = obj(snapshot?.last_updated_ts);
  const mc = obj(snapshot?.memory_context);
  const episode = obj(mc.last_episode);

  return (
    <div style={{ fontSize: 13 }}>
      {entries.length === 0 && <div style={{ color: "#999" }}>No counts available.</div>}
      {entries.map(([k, v]) => (
        <div key={k} style={{ display: "flex", justifyContent: "space-between" }} title={`snapshot.counts.${k}`}>
          <span style={{ color: "#666" }}>{k}</span>
          <strong>{v}</strong>
        </div>
      ))}

      <div
        data-testid="vault-flags"
        title="snapshot.coherence_flags"
        style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: "2px 10px", fontSize: 12 }}
      >
        {FLAGS.map((f) => (
          <span key={f} data-testid={`flag-${f}`} title={`snapshot.coherence_flags.${f}`}>
            <span style={{ color: "#666" }}>{f.replace(/_ok$/, "")}</span>{" "}
            <strong data-word={flagWord(flags[f])}>{flagWord(flags[f])}</strong>
          </span>
        ))}
      </div>

      <div
        data-testid="vault-stores"
        title="snapshot.last_updated_ts"
        style={{ marginTop: 6, display: "flex", flexWrap: "wrap", gap: "2px 8px", fontSize: 11, color: "#666" }}
      >
        {STORES.map((st) => (
          <span key={st} data-testid={`store-${st}`} title={`snapshot.last_updated_ts.${st} · last updated ${stamp(lts[st])}`}>
            {st}
          </span>
        ))}
      </div>

      <div
        data-testid="vault-episode"
        title={`snapshot.memory_context.last_episode.episode_id ${shown(episode.episode_id)} · snapshot.memory_context.last_updated_ts ${stamp(mc.last_updated_ts)}`}
        style={{ marginTop: 6, fontSize: 12 }}
      >
        <span style={{ color: "#666" }}>last episode</span>{" "}
        <span title="snapshot.memory_context.last_episode.sentiment">{shown(episode.sentiment)}</span>
        {" · weight "}
        <span title="snapshot.memory_context.last_episode.weight">{shown(episode.weight)}</span>
      </div>

      <Link to="/vault" style={{ display: "inline-block", marginTop: 8 }}>
        Open Vault →
      </Link>
    </div>
  );
}
