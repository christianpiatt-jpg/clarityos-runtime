// v1 user chip — MODIFIED to accept an optional ``name`` prop so the
// desktop can display the signed-in user.
import styles from "./UserIdentityChip.module.css";

interface Props {
  name?: string;
}

export default function UserIdentityChip({ name }: Props = {}) {
  return <div className={styles.chip}>{name && name.trim() ? name : "operator"}</div>;
}
