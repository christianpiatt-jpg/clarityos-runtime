import { Link } from "react-router-dom";

import Card from "../components/Card";
import Footer from "../components/Footer";
import LandingLayout from "../components/LandingLayout";

/**
 * Terms — placeholder. Real terms-of-service content lands in a
 * later card.
 */
export default function TermsRoute() {
  return (
    <LandingLayout>
      <Card>
        <h1>Terms</h1>
        <p className="pocket-muted">
          Terms of service are coming. This is a placeholder so the
          landing page footer link resolves and deep-link sharing
          works.
        </p>
        <p>
          <Link to="/landing">&larr; Back to landing</Link>
        </p>
      </Card>
      <Footer />
    </LandingLayout>
  );
}
