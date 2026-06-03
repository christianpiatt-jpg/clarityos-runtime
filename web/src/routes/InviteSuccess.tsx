import { useLocation, useParams } from "react-router-dom";

// Public post-checkout success page for the invite flow. Stripe redirects the
// browser here after a successful subscription:
//   /invite/:token/success?plan=<plan>&session_id=<CHECKOUT_SESSION_ID>
// Read-only confirmation — reads session_id / plan from the query string and the
// token from the route params. No API calls, no Stripe fetch, no backend.
export default function InviteSuccess() {
  const { token } = useParams<{ token: string }>();
  const query = new URLSearchParams(useLocation().search);
  const sessionId = query.get("session_id") || "";
  const plan = query.get("plan") || "";

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <div
        style={{ maxWidth: 420, width: "100%" }}
        data-invite-token={token || ""}
      >
        <div className="panel">
          <h2>SUBSCRIPTION CONFIRMED</h2>
          <p className="muted" style={{ marginTop: 4, marginBottom: 16 }}>
            Your subscription is confirmed.
          </p>

          <p style={{ margin: "8px 0" }}>
            <strong>Session ID:</strong>{" "}
            <span style={{ wordBreak: "break-all", fontFamily: "monospace" }}>
              {sessionId || "—"}
            </span>
          </p>
          <p style={{ margin: "8px 0 20px" }}>
            <strong>Plan:</strong> {plan || "—"}
          </p>

          <a className="btn btn-block" href="https://cockpit.pro-mediations.com">
            ENTER COCKPIT
          </a>
        </div>
      </div>
    </div>
  );
}
