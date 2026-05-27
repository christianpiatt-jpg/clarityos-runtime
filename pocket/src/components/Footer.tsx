import { Link } from "react-router-dom";

/**
 * Footer — the standard footer for marketing-facing routes
 * (landing, privacy, terms). Quiet, low-contrast, doesn't fight
 * the page above it. Links go to stub routes inside the SPA so
 * deep-link sharing works.
 */
export default function Footer() {
  return (
    <footer className="pkt-footer">
      <div className="pkt-footer-brand">Powered by ClarityOS</div>
      <nav className="pkt-footer-links" aria-label="Footer">
        <Link to="/privacy">Privacy</Link>
        <span className="pkt-footer-sep" aria-hidden="true">
          &middot;
        </span>
        <Link to="/terms">Terms</Link>
      </nav>
    </footer>
  );
}
