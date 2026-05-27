import { TextareaHTMLAttributes, ReactNode, useId } from "react";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: ReactNode;
  error?: ReactNode;
  hint?: ReactNode;
}

/**
 * Textarea — same shape as Input but for multi-line entry.
 * Defaults to ``rows={4}`` so the affordance is obvious on mobile.
 */
export default function Textarea({
  label,
  error,
  hint,
  className = "",
  id,
  rows = 4,
  ...rest
}: TextareaProps) {
  const generatedId = useId();
  const inputId = id ?? `pkt-textarea-${generatedId}`;
  return (
    <div className={`pkt-field ${error ? "is-error" : ""}`}>
      <label htmlFor={inputId} className="pkt-field-label">
        {label}
      </label>
      <textarea
        {...rest}
        id={inputId}
        rows={rows}
        className={`pkt-textarea ${className}`}
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
