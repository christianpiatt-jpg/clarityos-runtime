// Clarity v1.5 — operator-grade transform.
//
// Voice contract:
//   • Terse. No first-person. No hedging.
//   • Section order: DECISIONS → WARNINGS → CONTRADICTIONS → BODY → META
//   • Empty sections omitted (META is always shown — it's the runtime trace).
//   • Each section labels its source interpreter [galileo|tizzy|markov].
//   • Decisions and warnings are deduplicated case-insensitively.
//
// Pure function. No I/O. Stable on the same input.

import type { ClarityObject, PressureSignature } from "./langbridg";

export type ClarityKind =
  | "decisions"
  | "warnings"
  | "contradictions"
  | "body"
  | "meta";
export type Interpreter = "galileo" | "tizzy" | "markov";

export interface ClaritySection {
  kind: ClarityKind;
  interpreter: Interpreter;
  body: string;
}

export interface ClarityRender {
  text: string;
  sections: ClaritySection[];
  interpreters: Interpreter[];
  pressure: PressureSignature;
}

function dedupe(list: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const x of list) {
    const t = x.trim();
    if (!t) continue;
    const k = t.toLowerCase();
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(t);
  }
  return out;
}

export function transform(c: ClarityObject): ClarityRender {
  const sections: ClaritySection[] = [];
  const interpreters = new Set<Interpreter>();

  const decisions = dedupe(c.decisions);
  if (decisions.length) {
    sections.push({
      kind: "decisions",
      interpreter: "markov",
      body: decisions.map((d, i) => `${i + 1}. ${d}`).join("\n"),
    });
    interpreters.add("markov");
  }

  const warnings = dedupe(c.warnings);
  if (warnings.length) {
    sections.push({
      kind: "warnings",
      interpreter: "markov",
      body: warnings.map((w) => `! ${w}`).join("\n"),
    });
    interpreters.add("markov");
  }

  if (c.contradictions.length) {
    sections.push({
      kind: "contradictions",
      interpreter: "markov",
      body: c.contradictions
        .map((x, i) => `${i + 1}. [${x.kind}] ${x.a} ⟷ ${x.b}`)
        .join("\n"),
    });
    interpreters.add("markov");
  }

  // Prefer the tone-stripped body when it's actually different and not empty.
  const stripped = c.toneStripped?.trim() ?? "";
  const source = c.source?.trim() ?? "";
  const body = stripped && stripped !== source ? stripped : source;
  if (body) {
    sections.push({
      kind: "body",
      interpreter: "tizzy",
      body,
    });
    interpreters.add("tizzy");
  }

  // META is always present — it's the runtime trace, useful for the operator.
  const p = c.pressure;
  sections.push({
    kind: "meta",
    interpreter: "galileo",
    body: [
      `sentences=${p.sentenceCount}`,
      `imperatives=${p.imperatives}`,
      `urgency=${p.urgencyWords}`,
      `hedge=${p.hedgeRatio}`,
      `contradictions=${p.contradictions}`,
    ].join("  "),
  });
  interpreters.add("galileo");

  const text = sections
    .map((s) => `${s.kind.toUpperCase()} [${s.interpreter}]\n${s.body}`)
    .join("\n\n");

  return {
    text,
    sections,
    interpreters: Array.from(interpreters),
    pressure: c.pressure,
  };
}
