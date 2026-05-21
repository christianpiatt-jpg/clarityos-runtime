// v1 sidebar — MODIFIED to accept children rendered below the static
// NavItems (B1-thread-below-nav layout for the desktop integration).
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
  "Session",
  // v63 / Units 47 + 48 — Read-only history + vault inspector.
  "History",
  "Operator Vault",
  // v64 / Unit 67 — Model preferences.
  "Model",
  // v65 / Unit 69 — Provider health dashboard.
  "Provider Health",
  // v68 / Unit 73 — Unified provider dashboard (health + models + config).
  "Providers",
  // v69 / Unit 74 — EL/INS reasoning-stability operator.
  "EL/INS",
  "EL/INS Macro",
  // v70 / Unit 77 — unified EL/INS dashboard.
  "EL/INS Dashboard",
  // v71 / Unit 78 — EL/INS export (JSON + PDF) for Founding Cohort.
  "EL/INS Export",
  // v72 / Units 80+81 — anomaly alerts + organizational roll-up.
  "EL/INS Anomalies",
  "EL/INS Roll-Up",
  // v73 / Units 82+83 — operator + org timeline.
  "Timeline",
  "Org Timeline",
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
