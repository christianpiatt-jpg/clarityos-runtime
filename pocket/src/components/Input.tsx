import { InputHTMLAttributes, ReactNode, useId } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: ReactNode;
  /** Inline error text under the input. */
  error?: ReactNode;
  /** Helper text under the input (rendered when no error). */
  hint?: ReactNode;
}

/**
 * Input — labelled text field with optional error + hint slot.
 * Uses React's ``useId`` for the label/input association so the
 * pairing is stable + accessible.
 */
export default function Input({
  label,
  error,
  hint,
  className = "",
  id,
  ...rest
}: InputProps) {
  const generatedId = useId();
  const inputId = id ?? `pkt-input-${generatedId}`;
  return (
    <div className={`pkt-field ${error ? "is-error" : ""}`}>
      <label htmlFor={inputId} className="pkt-field-label">
        {label}
      </label>
      <input
        {...rest}
        id={inputId}
        className={`pkt-input ${className}`}
        aria-invalid={error ? true : undefined}
      />
      {error ? (
        <div className="pkt-field-error">{error}</div>
      ) : hint ? (
        <div className="pkt-field-hint">{hint}</div>
      ) : null}
    </div>
  );
}
