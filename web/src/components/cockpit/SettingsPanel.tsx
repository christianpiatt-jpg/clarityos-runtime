// components/cockpit/SettingsPanel.tsx — minimal settings surface.
// Today: device id (mesh sync key) + Dewey-only sharing notice.

export interface SettingsPanelProps {
  deviceId: string;
}

export default function SettingsPanel({ deviceId }: SettingsPanelProps) {
  return (
    <div style={{ fontSize: 13 }}>
      <div><strong>Device id:</strong> <code>{deviceId}</code></div>
      <div style={{ marginTop: 4, color: "#666" }}>
        Stable per-browser, persisted in localStorage. Used as the mesh sync key.
      </div>
      <div style={{
        marginTop: 8,
        padding: 6,
        background: "#f6f6fa",
        borderLeft: "3px solid #88a",
        fontSize: 12,
        color: "#445",
      }}>
        <strong>Privacy:</strong> only Dewey-shaped metadata leaves this device
        (counts, last_updated_ts, coherence flags). Vault items, event text,
        scenario text, and embedding vectors stay local.
      </div>
    </div>
  );
}
