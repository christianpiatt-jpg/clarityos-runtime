import { Link } from "react-router-dom";

import Card from "../components/Card";

/**
 * Pocket Home — landing card.
 *
 * Minimal greeting + the 4 functional entry points so a first-time
 * visitor can immediately see what's here without crawling the nav.
 */
export default function HomeRoute() {
  return (
    <Card>
      <h1>Pocket</h1>
      <p className="pocket-muted">
        ClarityOS phone-sized web surface. Separate runtime from the
        cockpit and the Expo phone app.
      </p>
      <p className="pocket-faint" style={{ fontSize: 13 }}>
        Skeleton v0.3.2 &mdash; somatic UI pass.
      </p>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 8,
          marginTop: 16,
        }}
      >
        <Link
          to="/runtime"
          className="pkt-btn pkt-btn--secondary pkt-btn--md is-block"
        >
          Runtime
        </Link>
        <Link
          to="/clarify"
          className="pkt-btn pkt-btn--secondary pkt-btn--md is-block"
        >
          Clarify
        </Link>
        <Link
          to="/me"
          className="pkt-btn pkt-btn--secondary pkt-btn--md is-block"
        >
          Me
        </Link>
        <Link
          to="/runs"
          className="pkt-btn pkt-btn--secondary pkt-btn--md is-block"
        >
          Runs
        </Link>
      </div>
    </Card>
  );
}
