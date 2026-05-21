import styles from "./NavItem.module.css";

export default function NavItem({ label }: { label: string }) {
  return (
    <button type="button" className={styles.item}>
      {label}
    </button>
  );
}
