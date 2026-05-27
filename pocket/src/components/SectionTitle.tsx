import { HTMLAttributes, ReactNode } from "react";

interface SectionTitleProps extends HTMLAttributes<HTMLHeadingElement> {
  children: ReactNode;
  /** Optional small description shown below the title. */
  description?: ReactNode;
}

/**
 * SectionTitle — the ``<h2>``-equivalent header between cards. Has
 * a quieter color than the page heading so primary attention stays
 * on the card content, not the label.
 */
export default function SectionTitle({
  children,
  description,
  className = "",
  ...rest
}: SectionTitleProps) {
  return (
    <div className="pkt-section">
      <h2 {...rest} className={`pkt-section-title ${className}`}>
        {children}
      </h2>
      {description ? (
        <p className="pkt-section-desc">{description}</p>
      ) : null}
    </div>
  );
}
