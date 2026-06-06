// Phase 6 — shared error surface.
//
// Catches render-time errors in the wrapped subtree and shows an inline
// fallback (message + Try again + Reload) instead of a white screen. Before
// this, only Cockpit had a private panel-level boundary; App.tsx now wraps the
// whole route tree with this component so EVERY route is crash-protected.
//
// No remote logging — the app has no outbound telemetry; the error is surfaced
// to the operator inline.
import React from "react";

interface Props {
  children: React.ReactNode;
  /** Optional heading for context, e.g. "Application error" / "Panel error". */
  label?: string;
}
interface State {
  error: Error | null;
}

export default class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(_error: Error, _info: React.ErrorInfo): void {
    // Intentionally inline-only (no remote logging).
  }

  private reset = (): void => this.setState({ error: null });

  render(): React.ReactNode {
    if (this.state.error) {
      return (
        <div role="alert" data-testid="error-boundary" style={boxStyle}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>
            {this.props.label ?? "Something went wrong"}
          </div>
          <div
            data-testid="error-boundary-message"
            style={{ marginBottom: 10, wordBreak: "break-word" }}
          >
            {this.state.error.message || "An unexpected error occurred."}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              data-testid="error-boundary-retry"
              onClick={this.reset}
              style={btnStyle}
            >
              Try again
            </button>
            <button
              type="button"
              onClick={() => window.location.reload()}
              style={btnStyle}
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return <>{this.props.children}</>;
  }
}

const boxStyle: React.CSSProperties = {
  margin: 16,
  padding: 16,
  border: "1px solid #E74C3C",
  borderRadius: 6,
  background: "rgba(231, 76, 60, 0.08)",
  color: "#E74C3C",
  fontFamily: "var(--font-sans, sans-serif)",
  fontSize: 13,
  lineHeight: 1.5,
};

const btnStyle: React.CSSProperties = {
  background: "transparent",
  border: "1px solid #E74C3C",
  color: "#E74C3C",
  padding: "4px 12px",
  fontSize: 12,
  cursor: "pointer",
  borderRadius: 4,
};
