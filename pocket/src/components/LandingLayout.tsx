import { ReactNode } from "react";

interface LandingLayoutProps {
  children: ReactNode;
}

/**
 * LandingLayout — minimal centered column for marketing-facing
 * surfaces (``/landing``, ``/privacy``, ``/terms``). Inherits all
 * design tokens from app.css (colors, type, spacing) and respects
 * the same dark/light variables as the rest of Pocket.
 *
 * Width cap is the same ``--max-w`` (480px) the app uses elsewhere
 * so the visual rhythm doesn't change between marketing and app
 * routes.
 */
export default function LandingLayout({ children }: LandingLayoutProps) {
  return <div className="pkt-landing">{children}</div>;
}
