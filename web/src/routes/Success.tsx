// Post-checkout landing. Unauthenticated — the buyer has paid but has not
// signed in yet; the webhook has just emailed them a magic link.
//
// Echoing the address back is the point of this page: it is what tells a buyer
// whether the purchase used the inbox they are actually watching. The address
// is read from ?email= when the platform supplies it and the page degrades to
// generic copy when it does not — see the note in App.tsx / the FRAGO return.
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

export default function Success() {
  const [params] = useSearchParams();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    const e = params.get("email");
    if (e && e.includes("@")) setEmail(e);
  }, [params]);

  return (
    <div className="panel" style={{ maxWidth: 620, margin: "48px auto" }}>
      <h1 style={{ marginTop: 0 }}>✓ Payment received</h1>

      <p>
        Check your email — we&rsquo;ve just sent your sign-in link
        {email ? <> to <strong>{email}</strong></> : null}.
      </p>

      <p className="muted">
        Click it and you&rsquo;re in. The link works once and expires; if it
        doesn&rsquo;t arrive in a few minutes, check spam or request another
        below.
      </p>

      <p style={{ marginTop: 24 }}>
        <a className="btn" href="https://pro-mediations.com/enter/">
          SEND ANOTHER LINK
        </a>
      </p>

      <p className="muted" style={{ fontSize: "0.8rem", marginTop: 20 }}>
        Already signed in on this device? <Link to="/cockpit">Go to the app</Link>.
      </p>
    </div>
  );
}
