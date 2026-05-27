import { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost";
type ButtonSize = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Stretch to fill the parent's width. Useful for mobile forms. */
  block?: boolean;
  children: ReactNode;
}

/**
 * Button — three variants (primary / secondary / ghost), two
 * sizes. Block-width via the ``block`` prop. Always honours
 * disabled state.
 */
export default function Button({
  variant = "primary",
  size = "md",
  block = false,
  className = "",
  children,
  type = "button",
  ...rest
}: ButtonProps) {
  const classes = [
    "pkt-btn",
    `pkt-btn--${variant}`,
    `pkt-btn--${size}`,
    block ? "is-block" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <button {...rest} type={type} className={classes}>
      {children}
    </button>
  );
}
