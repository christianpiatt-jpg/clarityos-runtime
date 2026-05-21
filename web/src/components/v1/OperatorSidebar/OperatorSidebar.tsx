// v1 sidebar — accepts children rendered below the 6 static NavItems
// (B1-thread-below-nav). The web client puts its thread list there.
import type { ReactNode } from "react";
import styles from "./OperatorSidebar.module.css";
import NavItem from "../NavItem/NavItem";

const NAV_ITEMS = [
  "Home",
  "Threads",
  "Projects",
  "Emotional Physics",
  "Personal ELINS",
  "Library",
  "Settings",
] as const;

interface Props {
  children?: ReactNode;
  /** When provided, NavItem clicks invoke this with the item's label.
   *  When omitted, items render as static visuals (harness behaviour). */
  onNavigate?: (label: string) => void;
  /** Label of the currently active nav item (for highlighting). */
  activeNav?: string;
}

export default function OperatorSidebar({
  children, onNavigate, activeNav,
}: Props = {}) {
  return (
    <nav className={styles.sidebar}>
      {NAV_ITEMS.map((label) => (
        <NavItem
          key={label}
          label={label}
          active={activeNav === label}
          onClick={onNavigate ? () => onNavigate(label) : undefined}
        />
      ))}
      {children}
    </nav>
  );
}
