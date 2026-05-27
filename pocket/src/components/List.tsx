import { HTMLAttributes, LiHTMLAttributes, ReactNode } from "react";

/**
 * List — vertical stack of ListItem. Uses ``<ul>`` semantics so
 * screen readers correctly announce the count + sequence.
 */
export function List({
  children,
  className = "",
  ...rest
}: HTMLAttributes<HTMLUListElement> & { children: ReactNode }) {
  return (
    <ul {...rest} className={`pkt-list ${className}`}>
      {children}
    </ul>
  );
}

/**
 * ListItem — single row in a List. Optionally accepts a leading
 * + trailing slot for chips/icons; the body is the children.
 */
interface ListItemProps extends LiHTMLAttributes<HTMLLIElement> {
  children: ReactNode;
  leading?: ReactNode;
  trailing?: ReactNode;
}

export function ListItem({
  children,
  leading,
  trailing,
  className = "",
  ...rest
}: ListItemProps) {
  return (
    <li {...rest} className={`pkt-list-item ${className}`}>
      {leading ? <span className="pkt-list-item-leading">{leading}</span> : null}
      <span className="pkt-list-item-body">{children}</span>
      {trailing ? (
        <span className="pkt-list-item-trailing">{trailing}</span>
      ) : null}
    </li>
  );
}
