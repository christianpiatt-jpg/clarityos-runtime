import styles from "./InputBar.module.css";
import InputField from "../InputField/InputField";
import InputActions from "../InputActions/InputActions";

export default function InputBar() {
  return (
    <div className={styles.bar}>
      <InputField />
      <InputActions />
    </div>
  );
}
