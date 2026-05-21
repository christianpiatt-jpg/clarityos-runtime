import styles from "./OperatorSidebar.module.css";
import NavItem from "../NavItem/NavItem";

const NAV_ITEMS = [
  "Home",
  "Threads",
  "Projects",
  "Emotional Physics",
  "Library",
  "Settings",
] as const;

export default function OperatorSidebar() {
  return (
    <nav className={styles.sidebar}>
      {NAV_ITEMS.map((label) => (
        <NavItem key={label} label={label} />
      ))}
    </nav>
  );
}
