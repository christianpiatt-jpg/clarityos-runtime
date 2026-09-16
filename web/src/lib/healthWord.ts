/**
 * #151 -- the word a surface shows for a failed /health probe. ONE vocabulary
 * on the web and the phone (phone/lib/wire.ts healthWord is this function):
 * a 401 is "not signed in", a 403 "not permitted", any other status names
 * itself ("HTTP <n>") and never the server's message string (a server body
 * is not a client word); no status at all -- the backend could not be
 * reached -- is "unreachable". (/health is probed without a session, so the
 * two auth words are reachable only if that changes.)
 */
export function healthWord(status: unknown): string {
  const n = typeof status === "number" && Number.isFinite(status) ? status : 0;
  if (n === 401) return "not signed in";
  if (n === 403) return "not permitted";
  if (n > 0) return `HTTP ${n}`;
  return "unreachable";
}
