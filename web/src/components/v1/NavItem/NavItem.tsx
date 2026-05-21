import styles from "./NavItem.module.css";

interface Props {
  label: string;
  onClick?: () => void;
  active?: boolean;
}

export default function NavItem({ label, onClick, active }: Props) {
  const cls = active ? `${styles.item} ${styles.itemActive}` : styles.item;
  return (
    <button type="button" className={cls} onClick={onClick}>
      {label}
    </button>
  );
}
