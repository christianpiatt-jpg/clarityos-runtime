import { Link } from "react-router-dom";

import Card from "../components/Card";
import Footer from "../components/Footer";
import LandingLayout from "../components/LandingLayout";
import { getStripeCheckoutUrl, isStripePlaceholder } from "../lib/stripe";

/**
 * Landing — Pocket's product-facing entry point.
 *
 * Structure:
 *   * Hero: headline + subhead + primary CTA ("Open Pocket" -> /)
 *   * Card: Founding Members offer + secondary CTA ("Join" -> Stripe)
 *   * Footer: powered-by + privacy + terms
 *
 * Stripe link is a placeholder; the URL comes from
 * ``getStripeCheckoutUrl``. ``isStripePlaceholder`` controls a
 * small inline note + the link target (no new tab while it's a
 * placeholder).
 */
export default function LandingRoute() {
  const foundingUrl = getStripeCheckoutUrl("founding");
  const isPlaceholder = isStripePlaceholder(foundingUrl);

  return (
    <LandingLayout>
      <section className="pkt-landing-hero">
        <h1 className="pkt-landing-headline">Clarity when you need it.</h1>
        <p className="pkt-landing-subhead">
          Pocket is your always-on clarity surface.
        </p>
        <Link
          to="/"
          className="pkt-btn pkt-btn--primary pkt-btn--md is-block"
        >
          Open Pocket
        </Link>
      </section>

      <Card>
        <h2>Founding Members</h2>
        <p className="pocket-muted">
          Early access, priority features, direct operator support.
        </p>
        <a
          href={foundingUrl}
          className="pkt-btn pkt-btn--secondary pkt-btn--md is-block"
          target={isPlaceholder ? undefined : "_blank"}
          rel="noopener noreferrer"
          aria-label="Become a Founding Member"
        >
          Join
        </a>
        {isPlaceholder ? (
          <p className="pkt-landing-note">
            Stripe link is a placeholder &mdash; paste the real
            Payment Link into{" "}
            <code>pocket/src/lib/stripe.ts</code>.
          </p>
        ) : null}
      </Card>

      <Footer />
    </LandingLayout>
  );
}
