import { Link } from "react-router-dom";

import { getBackendUrl } from "../api/client";

/**
 * Pocket Runtime screen.
 *
 * PHONE-native runtime view. Surfaces Pocket's OWN deploy metadata
 * (build version + backend URL it was wired to). NOT a DOM embed
 * of the cockpit's Node runtime panel and NOT an API mirror of it.
 *
 * The cockpit's Node runtime panel reads Cloud Run env vars on its
 * own service (``K_SERVICE`` / ``K_REVISION`` / ``ENVIRONMENT``).
 * Pocket lives on a different Cloud Run service and surfaces its
 * own build-time injected metadata. Keeping them independent is
 * the whole reason this is a separate SPA.
 */
export default function RuntimeRoute() {
  const backendUrl = getBackendUrl();
  const buildVersion =
    (import.meta.env.VITE_BUILD_VERSION as string | undefined) ?? "";

  return (
    <section className="pocket-runtime">
      <h1>Runtime</h1>
      <p className="pocket-status">
        <span className="pocket-status-dot" /> runtime OK
      </p>

      <dl>
        <dt>Build version</dt>
        <dd>{buildVersion || "(unset)"}</dd>

        <dt>Backend URL</dt>
        <dd>{backendUrl || "(not configured)"}</dd>
      </dl>

      <p>
        <Link to="/">&larr; Home</Link>
      </p>
    </section>
  );
}
