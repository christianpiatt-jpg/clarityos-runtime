/**
 * Stripe checkout — placeholder.
 *
 * Pocket does not yet integrate the Stripe SDK. This module wires
 * the UI to a typed function so the call sites are stable; the
 * actual checkout URLs are placeholders until you paste the real
 * Stripe Payment Link / Checkout URLs into ``STRIPE_CHECKOUT_URLS``
 * below.
 *
 * Why placeholders (not SDK):
 *   * No browser bundle bloat from ``@stripe/stripe-js``
 *   * Payment Links are sufficient for one-shot subscribe flows
 *   * Lets the surface ship + look real today; swap in the real
 *     URLs the moment they're created in the Stripe dashboard
 *
 * When swapping in real URLs:
 *   1. Create a Payment Link per tier in the Stripe dashboard
 *   2. Replace each ``PLACEHOLDER_*`` URL below
 *   3. Optional: set success_url + cancel_url on the Payment Link
 *      to return users to ``/me?welcome=1`` or similar
 *
 * If/when client-side ``redirectToCheckout`` is needed (e.g. dynamic
 * prices, server-confirmed sessions), THEN add the SDK and a
 * backend endpoint. For now, an ordinary ``<a href>`` is enough.
 */

export type StripeTier = "founding" | "monthly" | "annual";

/** Stripe Payment Link URLs per tier. ``founding`` is live (real
 *  Checkout Link from the Stripe dashboard); ``monthly`` and
 *  ``annual`` are still placeholders until those tiers are created
 *  in Stripe. ``isStripePlaceholder`` below lets the UI render a
 *  small "Stripe link is a placeholder" note for the unfilled
 *  tiers without changing call sites. */
const STRIPE_CHECKOUT_URLS: Record<StripeTier, string> = {
  founding: "https://buy.stripe.com/fZu9ATclDb3re3cgFB0VO00",
  monthly:  "https://buy.stripe.com/PLACEHOLDER_MONTHLY",
  annual:   "https://buy.stripe.com/PLACEHOLDER_ANNUAL",
};

export function getStripeCheckoutUrl(tier: StripeTier): string {
  return STRIPE_CHECKOUT_URLS[tier];
}

/** Returns true when the URL is still a placeholder. The landing
 *  page uses this to render a small "Stripe link is a placeholder"
 *  note + suppress ``target="_blank"`` (since clicking through
 *  to a placeholder host is just noise). */
export function isStripePlaceholder(url: string): boolean {
  return url.includes("PLACEHOLDER");
}
