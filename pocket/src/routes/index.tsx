import { Link } from "react-router-dom";

/**
 * Pocket Home — placeholder landing screen.
 *
 * The v0.3.0 scaffold ships with only this route and ``/runtime``.
 * Concrete operator screens (``/clarify``, ``/me``, ``/runs``, etc.)
 * land in v0.3.x cards.
 */
export default function HomeRoute() {
  return (
    <section className="pocket-home">
      <h1>Pocket</h1>
      <p>
        ClarityOS phone-sized web surface. Separate runtime from the
        cockpit (Node v0.2 at <code>cockpit.pro-mediations.com</code>) and
        the Expo native phone app under <code>/phone</code>.
      </p>
      <p>
        Surface skeleton v0.3.0 &mdash; concrete screens land in
        v0.3.x.
      </p>
      <p>
        <Link to="/runtime">View runtime &rarr;</Link>
      </p>
    </section>
  );
}
