/**
 * Web Surface v0.2.0 — demo upload view (Card A16).
 *
 * Registered as ``"upload_demo"``. URL:
 * ``/web-surface/v0.2/upload_demo``.
 *
 * Behaviour:
 *   * GET                            → empty form (no metadata).
 *   * POST + multipart/form-data     → classifier emits an
 *                                      ``upload`` action, handler
 *                                      parses the body, view
 *                                      surfaces filename /
 *                                      content-type / size.
 *
 * Template note:
 *   * The template engine has no conditionals, so the metadata
 *     block always renders. On GET (no upload) the values are
 *     empty strings and ``Size: 0 bytes``. That's the v0.2 UX
 *     trade-off documented in the card.
 *
 * Security:
 *   * ``filename`` and ``contentType`` come from the client and
 *     are HTML-escaped at the view boundary before substitution.
 *     A hostile filename like ``"><script>alert(1)</script>``
 *     becomes harmless escaped text in the rendered metadata.
 *   * The raw file ``data`` (bytes) is NEVER substituted into the
 *     template — only its length surfaces as ``size``. Bytes
 *     stay in memory and are garbage-collected after the
 *     response completes.
 *
 * Defensive coercion:
 *   * ``ctx.params.files`` may be:
 *       - undefined (GET, no upload),
 *       - a string ("files" passed via querystring, would be a
 *         routing accident — defensive guard),
 *       - the actual ``Record<string, UploadedFile>`` from the
 *         upload handler.
 *     The view checks shape before reading ``["file"]``.
 */
import { WebSurfaceV0_2_View as V } from "../viewContract";
import { registerView, ViewDefinition } from "../viewRegistry";
import { UploadedFile } from "../multipartParser";


function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


/** Pull the ``files`` map out of ctx.params with a defensive
 *  shape check. Returns ``{}`` for any input that isn't a plain
 *  object so the rest of ``render`` can use Object semantics
 *  without further checks. */
function _readFiles(
  ctx: V.RenderContext,
): Record<string, UploadedFile> {
  const raw = (ctx.params as Record<string, unknown> | undefined)?.files;
  if (
    raw === null ||
    raw === undefined ||
    typeof raw !== "object" ||
    Array.isArray(raw)
  ) {
    return {};
  }
  return raw as Record<string, UploadedFile>;
}


/** Returns true if ``f`` looks like an UploadedFile (has all
 *  three load-bearing fields). Defensive against a malformed
 *  ``files`` object from a direct programmatic dispatch. */
function _isUploadedFile(f: unknown): f is UploadedFile {
  if (f === null || typeof f !== "object") return false;
  const o = f as Record<string, unknown>;
  return (
    typeof o.filename === "string" &&
    typeof o.contentType === "string" &&
    o.data !== null &&
    o.data !== undefined &&
    typeof (o.data as { length?: unknown }).length === "number"
  );
}


/** Exported for tests + future programmatic re-registration. */
export const uploadDemoView: ViewDefinition = {
  template: "upload_demo",
  layout:   "standard",
  async render(ctx: V.RenderContext) {
    const files = _readFiles(ctx);
    const candidate = files["file"];
    const file = _isUploadedFile(candidate) ? candidate : null;

    return {
      title:       escapeHtml("Upload Demo"),
      subtitle:    escapeHtml("Upload Demo"),
      filename:    escapeHtml(file?.filename ?? ""),
      contentType: escapeHtml(file?.contentType ?? ""),
      // ``size`` is a number — the template engine stringifies
      // via ``String(value)`` so 0 / 42 / etc. substitute as-is.
      size:        file ? file.data.length : 0,
    };
  },
};


// Side-effect registration: the first import of this module
// installs ``upload_demo`` in the registry.
registerView("upload_demo", uploadDemoView);
