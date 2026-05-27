/**
 * Pocket — Loading primitive.
 *
 * Used across screens for in-flight network requests. Keeps the
 * surface coherent (one spinner shape, one label convention)
 * without dragging in a UI library.
 */
interface LoadingProps {
  /** Optional label shown alongside the dot. Default: "Loading…" */
  label?: string;
}

export default function Loading({ label = "Loading…" }: LoadingProps) {
  return (
    <div className="pocket-loading" role="status" aria-live="polite">
      <span className="pocket-loading-dot" />
      <span>{label}</span>
    </div>
  );
}
