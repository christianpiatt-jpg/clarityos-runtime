import { HTMLAttributes, ReactNode } from "react";

/**
 * Card — the surface that holds related content. Centered on
 * mobile, bordered + slightly elevated. The only structural
 * primitive that defines a "panel" in the Pocket UI.
 */
interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  /** Defaults to ``true``. Disable for tight content (e.g. lists). */
  padded?: boolean;
}

export default function Card({
  children,
  padded = true,
  className = "",
  ...rest
}: CardProps) {
  const classes = ["pkt-card", padded ? "is-padded" : "", className]
    .filter(Boolean)
    .join(" ");
  return (
    <div {...rest} className={classes}>
      {children}
    </div>
  );
}
