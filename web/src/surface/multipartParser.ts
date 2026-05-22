/**
 * Web Surface v0.2.0 — multipart/form-data parser (Card A16).
 *
 * Pure, deterministic, in-memory-only multipart parser.
 * Counterpart to ``formParser.ts``: where the form parser handles
 * ``application/x-www-form-urlencoded`` text bodies, this one
 * handles ``multipart/form-data`` binary bodies for file uploads.
 *
 * Properties (load-bearing):
 *   * No disk writes. Ever. Files live in memory only for the
 *     duration of the request — the upload handler hands them
 *     to the view's ``render(ctx)``, which finishes the response,
 *     and then the Buffer is garbage-collected.
 *   * No streaming. The whole body is parsed in one pass. v0.2.0
 *     uses a small bounded request body (the deploy gate is off
 *     anyway); a streaming parser is a future card.
 *   * No external dependencies. Plain ``Buffer`` + the standard
 *     ``Buffer.indexOf`` for boundary scanning.
 *   * Pure: same (body, boundary) in → same MultipartResult out.
 *
 * Edge-cases the parser handles:
 *   * Empty body / no parts found → ``{fields: {}, files: {}}``.
 *   * Part without Content-Disposition header → skipped silently
 *     (defensive: ignore garbage instead of throwing).
 *   * File parts without Content-Type → default
 *     ``application/octet-stream``.
 *   * Trailing CRLF between content and next boundary → stripped
 *     from the content. This is the LOAD-BEARING bytes-integrity
 *     bug to avoid: every multipart spec has ``\r\n`` BEFORE the
 *     next boundary, and that ``\r\n`` belongs to the framing,
 *     NOT to the file's content. Failing to strip it means every
 *     uploaded file silently grows by 2 bytes at the end.
 *   * Duplicate field names: last write wins (same convention as
 *     the form parser).
 *
 * Type contract:
 *   * ``UploadedFile.data`` is typed as ``Uint8Array`` (the most
 *     portable byte-array type). The actual runtime value is a
 *     ``Buffer``, which IS-A ``Uint8Array``, so callers can rely
 *     on ``.length`` and indexed-access; if they need Buffer-
 *     specific methods, they can ``Buffer.from(file.data)`` to
 *     re-narrow.
 */

/** Stable across-language wire shape for a single uploaded file. */
export interface UploadedFile {
  filename: string;
  contentType: string;
  data: Uint8Array;
}


/** Parsed shape: text fields + file uploads, separated. */
export interface MultipartResult {
  fields: Record<string, string>;
  files: Record<string, UploadedFile>;
}


/** Bytes of the CRLF sequence — interned once. */
const _CRLF = Buffer.from("\r\n");

/** Bytes of the double-CRLF header/body separator. */
const _CRLF_CRLF = Buffer.from("\r\n\r\n");


/**
 * Split a Buffer on every occurrence of ``delimiter``. Returns
 * the inter-delimiter chunks in order, with empty Buffer slices
 * for adjacent delimiters. Mirrors ``String.prototype.split``
 * semantics on a Buffer level.
 *
 * Exported for tests so the buffer-search logic can be exercised
 * directly without going through the full parse.
 */
export function _splitBuffer(body: Buffer, delimiter: Buffer): Buffer[] {
  const parts: Buffer[] = [];
  let start = 0;
  while (start <= body.length) {
    const idx = body.indexOf(delimiter, start);
    if (idx === -1) {
      parts.push(body.slice(start));
      break;
    }
    parts.push(body.slice(start, idx));
    start = idx + delimiter.length;
  }
  return parts;
}


/**
 * Split a part's bytes into ``[headers, content]`` on the first
 * ``\r\n\r\n`` separator. Returns empty content if no separator
 * is found (malformed part).
 *
 * The returned content has its trailing ``\r\n`` (the bytes
 * separating it from the next boundary) stripped — see the
 * module docstring for why this is critical.
 */
function _splitHeadersAndContent(part: Buffer): [Buffer, Buffer] {
  const idx = part.indexOf(_CRLF_CRLF);
  if (idx === -1) {
    return [part, Buffer.alloc(0)];
  }
  let content = part.slice(idx + _CRLF_CRLF.length);
  // Strip exactly one trailing CRLF (multipart framing). Anything
  // longer is content the user actually sent.
  if (
    content.length >= 2 &&
    content[content.length - 2] === 0x0d &&  // \r
    content[content.length - 1] === 0x0a     // \n
  ) {
    content = content.slice(0, content.length - 2);
  }
  return [part.slice(0, idx), content];
}


/**
 * Parse a multipart/form-data body. The ``boundary`` argument
 * comes from the request's Content-Type header (the classifier
 * extracts it before reaching here).
 *
 * Throws on no clearly defined error path — malformed parts are
 * skipped silently, and a wholly-unparseable body just yields
 * empty maps. This lets the surface return a degraded but valid
 * response rather than blowing up with a 500.
 */
export function parseMultipart(
  body: Buffer,
  boundary: string,
): MultipartResult {
  const delimiter = Buffer.from(`--${boundary}`);
  // First chunk is the preamble (before the first boundary —
  // usually empty); last chunk is whatever follows the closing
  // ``--boundary--`` marker (usually empty or a trailing CRLF).
  // Both are discarded.
  const parts = _splitBuffer(body, delimiter).slice(1, -1);

  const fields: Record<string, string> = {};
  const files: Record<string, UploadedFile> = {};

  for (const part of parts) {
    const [rawHeaders, rawContent] = _splitHeadersAndContent(part);
    const headers = rawHeaders.toString("utf8");

    // ``name="..."[; filename="..."]`` — the two parameters we
    // care about. The regex is permissive about whitespace but
    // strict about quoting (multipart spec mandates quoted
    // values for these parameters).
    const cd = /name="([^"]+)"(?:;\s*filename="([^"]*)")?/i.exec(headers);
    if (!cd) {
      continue;
    }
    const name = cd[1];
    const filename = cd[2];

    if (filename !== undefined) {
      // File part. Pick up Content-Type if the client sent one;
      // default to the canonical "unknown binary" mime otherwise.
      const ctMatch = /Content-Type:\s*([^\r\n]+)/i.exec(headers);
      const contentType = ctMatch ? ctMatch[1].trim() : "application/octet-stream";
      files[name] = {
        filename,
        contentType,
        data: rawContent,
      };
    } else {
      // Text field. ``.trim()`` to drop any stray whitespace
      // (multipart parts sometimes carry a leading newline from
      // implementations that aren't perfectly CRLF-clean).
      fields[name] = rawContent.toString("utf8").trim();
    }
  }

  return { fields, files };
}


/** Re-export the CRLF constant so tests + future callers don't
 *  have to rebuild it. */
export const MULTIPART_CRLF = _CRLF;
