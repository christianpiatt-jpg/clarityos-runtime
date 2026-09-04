// Checkout-cancelled landing. Unauthenticated. Nothing was charged; the buyer
// abandoned the Stripe session. No account was provisioned, so there is
// nothing to sign into and deliberately no link offer here.
import { Link } from "react-router-dom";

export default function Cancel() {
  return (
    <div className="panel" style={{ maxWidth: 620, margin: "48px auto" }}>
      <h1 style={{ marginTop: 0 }}>Checkout cancelled</h1>

      <p>Nothing was charged.</p>

      {/* #145 -- /plans folded into /membership, which needs a session
          this buyer does not have. The way back is the front page. */}
      <p style={{ marginTop: 24 }}>
        <Link className="btn" to="/">BACK TO THE FRONT PAGE</Link>
      </p>
    </div>
  );
}
