r"""Correct the truly_dead sweep. READ ONLY over source; writes analysis/ only.

Corrections, per CT-1 ORDER REV 3 item 2:
  1. response_model regex bug -- the class [\w\.\[\]]+ excludes comma and
     space, so Dict[str, Any] truncated to "Dict[str".
  2. caller-class field. "No fetch() caller" is not "dead": Stripe and an
     email client are callers. Searches phone/, desktop/ and the WP PHP
     plugins too -- the original sweep only ever read web/src.
  3. FOUND WHILE FIXING 1: every router-module route is attributed to
     "app.py". The line numbers are right; the file label is not.
  4. re-count what is ACTUALLY unreached.

A caller must be a real call-site: the path as a STRING, params included,
not a substring and not prose. Two rounds of my own false positives came
from matching a literal prefix -- /me/projects/{p} is NOT reached just
because /me/projects is.

Deletes nothing. Acts on nothing. Rules on nothing.
"""
import json, re, pathlib, collections

ROOT = pathlib.Path(r"C:\ClarityOS_Code")
A = ROOT / "analysis"
NL = chr(10)
QUOTES = '"' + "'" + chr(96)          # double, single, backtick

MODEL_RE = re.compile(r'response_model\s*=\s*([\w\.]+(?:\[[^\]]*\])?)')
ROUTE_RE = re.compile(r'@(?:app|\w+)\.(get|post|put|delete|patch)\(\s*"([^"]+)"([^)]*)\)')
COMMENT = re.compile(r'^\s*(//|\*|#)')

ROUTER_FILES = {"runtime_http.py": "", "acceptance_dashboard.py": "",
                "phase7_endpoint.py": "", "api/v1/emophysics.py": "/api/v1/emophysics"}

resolved, true_file = {}, {}


def scan(text, label, prefix=""):
    for m in ROUTE_RE.finditer(text):
        verb, path, tail = m.groups()
        line = text[:m.start()].count(NL) + 1
        full = (prefix + path) or path
        mm = MODEL_RE.search(tail)
        if mm:
            resolved["%s@%d" % (full, line)] = mm.group(1)
        if label != "app.py":
            true_file[full] = "%s:%d" % (label, line)


scan((ROOT / "app.py").read_text(encoding="utf-8", errors="replace"), "app.py")
for rel, pfx in ROUTER_FILES.items():
    p = ROOT / rel
    if p.exists():
        scan(p.read_text(encoding="utf-8", errors="replace"), rel, pfx)

SEARCH = [("spa", ROOT / "web" / "src", ("*.ts", "*.tsx")),
          ("phone", ROOT / "phone", ("*.ts", "*.tsx")),
          ("desktop", ROOT / "desktop" / "src", ("*.ts", "*.tsx")),
          ("wp-php", ROOT / "integrations", ("*.php",)),
          ("wp-php", ROOT / "wp-cockpit", ("*.php",)),
          ("wp-php", ROOT / "wp-sos-connector", ("*.php",))]

corpus = []
for label, base, globs in SEARCH:
    if not base.exists():
        continue
    for g in globs:
        for f in base.rglob(g):
            s = str(f)
            if "node_modules" in s or "__tests__" in s or "dist" in s:
                continue
            corpus.append((label, f, f.read_text(encoding="utf-8", errors="replace")))


def path_regex(path):
    parts = []
    for seg in path.strip("/").split("/"):
        if seg.startswith("{"):
            parts.append(r'(?:\$\{[^}]*\}|[^/' + QUOTES + r']+)')
        else:
            parts.append(re.escape(seg))
    body = "/" + "/".join(parts)
    return re.compile('[' + QUOTES + ']' + body + '(?:[' + QUOTES + '?/]|$)')


def find_callers(path):
    rx = path_regex(path)
    hits = []
    for lab, f, text in corpus:
        for line in text.split(NL):
            if COMMENT.match(line):
                continue
            if rx.search(line):
                hits.append({"class": lab, "file": str(f.relative_to(ROOT))})
                break
    return hits


EMAIL_LINK = {"/invite/{p}", "/invite/{p}/redeem",
              "/invite/{p}/checkout", "/invite/{p}/finalize"}

dead = json.loads((A / "sweep_truly_dead_2026-08-28.json").read_text())
out = []
for e in dead:
    path = e["path"]
    rec = dict(e)
    prod = e.get("producer") or ""
    ln = prod.rsplit(":", 1)[-1]

    fixed = resolved.get("%s@%s" % (path, ln))
    if fixed and fixed != e.get("model"):
        rec["model_was"] = e.get("model")
        rec["model"] = fixed

    tf = true_file.get(path)
    if tf and tf != prod:
        rec["producer_was"] = prod
        rec["producer"] = tf

    callers = find_callers(path)
    if "webhook" in path:
        rec["caller_class"] = "webhook"
        rec["caller"] = "Stripe posts to it. Load-bearing. No fetch() BY DESIGN."
    elif path in EMAIL_LINK:
        rec["caller_class"] = "email-link"
        rec["caller"] = "followed by an email link, not a fetch"
    elif callers:
        rec["caller_class"] = callers[0]["class"]
        rec["caller"] = sorted({c["file"] for c in callers})[:4]
    else:
        rec["caller_class"] = "none"
        rec["caller"] = None

    if path.startswith("/api/v1/emophysics"):
        rec["note"] = "Phase 1 SHADOW -- unreached AS SPECIFIED. Label, do not wire."
    out.append(rec)

(A / "sweep_truly_dead_corrected_2026-08-28.json").write_text(json.dumps(out, indent=1))

c = collections.Counter(r["caller_class"] for r in out)
print("total entries      ", len(out))
for k in ("spa", "phone", "desktop", "wp-php", "webhook", "email-link", "none"):
    if c.get(k):
        print("  %-12s %d" % (k, c[k]))
shadow = [r for r in out if "note" in r]
unreached = [r for r in out if r["caller_class"] == "none" and "note" not in r]
print("shadow (specified) ", len(shadow))
print("ACTUALLY UNREACHED ", len(unreached))
print("model corrections  ", len([r for r in out if "model_was" in r]))
for r in out:
    if "model_was" in r:
        print("    %s  %r -> %r" % (r["path"], r["model_was"], r["model"]))
print("producer mislabels ", len([r for r in out if "producer_was" in r]))
print()
print("ALIVE BUT LISTED DEAD:")
for r in out:
    if r["caller_class"] != "none":
        ev = r["caller"] if isinstance(r["caller"], str) else (r["caller"] or [""])[0]
        print("    %-30s %-11s %s" % (r["path"], r["caller_class"], ev))
