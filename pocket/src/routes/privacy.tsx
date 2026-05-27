import { Link } from "react-router-dom";

import Card from "../components/Card";
import Footer from "../components/Footer";
import LandingLayout from "../components/LandingLayout";

/**
 * Privacy — placeholder. Real policy content lands in a later card.
 */
export default function PrivacyRoute() {
  return (
    <LandingLayout>
      <Card>
        <h1>Privacy</h1>
        <p className="pocket-muted">
          Privacy policy is coming. This is a placeholder so the
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
