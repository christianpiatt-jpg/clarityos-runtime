/**
 * Web Surface v0.2.0 — file-upload handler (Card A16).
 *
 * Bridges the classifier's ``upload`` action to the existing
 * render pipeline. Sibling of ``formHandler.ts``: where the form
 * handler turns a URL-encoded string into ``params``, the upload
 * handler turns a multipart Buffer into ``{fields, files}`` and
 * spreads them into ``params``.
 *
 * Flow:
 *   1. Classifier emits
 *      ``{kind: "upload", view, rawBody, boundary, mode}``.
 *   2. Router dispatches here.
 *   3. ``parseMultipart`` separates text fields from file uploads.
 *      Files carry ``{filename, contentType, data: Uint8Array}``;
 *      fields are plain strings.
 *   4. ``executeRenderPipeline`` is called with ``params =
 *      {...fields, files}``. The named view reads
 *      ``ctx.params.files`` (a map keyed on the form input name)
 *      and surfaces metadata / bytes to the template.
 *
 * Properties:
 *   * No disk writes. No persistence. No storage layer.
 *   * No JSON-mode drift. The action's ``mode`` flows through to
 *     the pipeline unchanged — JSON uploads emit the canonical
 *     ``{view, params}`` envelope via ``defaultRenderer``. The
 *     envelope just carries an extra ``files`` key.
 *   * The pipeline's existing try/catch (Card A11) covers the
 *     full handler — a view that throws while consuming files
 *     surfaces as the structured 500 page, never as an
 *     exception bubble.
 *
 * Validation:
 *   * v0.2.0 doesn't run uploads through ``validateForm``. A
 *     future card can add an upload-shaped schema (per-file
 *     size limits, allowlist of content types, etc.) if needed.
 *
 * Determinism:
 *   * Same (rawBody, boundary, view, mode) in → same Response out.
 *   * Handler does not mutate the action, the registry, or any
 *     cache.
 */
import { WebSurfaceV0_2 } from "../contracts/webSurfaceV0_2";
import { WebSurfaceV0_2_View as V } from "./viewContract";
import { parseMultipart } from "./multipartParser";
import { executeRenderPipeline } from "./renderPipeline";


/** Shape of the classifier action this handler accepts. Held as
 *  a local type alias rather than importing the union variant so
 *  tests can construct a synthetic upload action without
 *  exporting an extra type from ``classifier.ts``. */
export interface UploadAction {
  kind: "upload";
  view: string;
  rawBody: Buffer;
  boundary: string;
  mode: V.Mode;
}


export async function handleUpload(
  action: UploadAction,
): Promise<WebSurfaceV0_2.Response> {
  const { fields, files } = parseMultipart(action.rawBody, action.boundary);

  return executeRenderPipeline({
    view:   action.view,
    params: {
      ...fields,
      files,
    },
    mode:   action.mode,
  });
}
