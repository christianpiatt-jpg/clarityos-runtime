/**
 * Pocket — Error primitive.
 *
 * Standard shape for surfacing API + form errors. Accepts either an
 * ``Error`` (we render ``.message``) or a plain string. Includes an
 * optional retry callback for screens that want a one-click retry.
 */
interface ErrorProps {
  error: Error | string | null;
  onRetry?: () => void;
  title?: string;
}

export default function ErrorBlock({
  error,
  onRetry,
  title = "Something went wrong",
}: ErrorProps) {
  if (error === null) return null;
  const message = typeof error === "string" ? error : error.message;
  return (
    <div className="pocket-error" role="alert">
      <div className="pocket-error-title">{title}</div>
      <div className="pocket-error-message">{message}</div>
      {onRetry ? (
        <button
          type="button"
          className="pocket-btn pocket-btn-small"
          onClick={onRetry}
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}
