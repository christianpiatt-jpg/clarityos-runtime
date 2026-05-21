// Langbridg v1.5 — raw text → structured ClarityObject.
//
// Three interpreters, fixed order:
//   • Galileo — structure: sentences, paragraphs, headings, bullets, code, quotes
//   • Tizzy   — tone: strip hedges, fillers, social padding
//   • Markov  — meaning: decisions, warnings, contradictions, pressure
//
// Pure-local. Deterministic. No I/O.

export type ContradictionKind = "negation" | "antonym" | "modal";

export interface PressureSignature {
  sentenceCount: number;
  imperatives: number;
  urgencyWords: number;
  contradictions: number;
  hedgeRatio: number; // hedges per sentence, rounded to 2 decimals
}

export interface ClarityObject {
  source: string;
  structure: {
    sentences: string[];
    paragraphs: string[][];
    headings: string[];
    bullets: string[];
    codeBlocks: string[];
    quotes: string[];
  };
  toneStripped: string;
  contradictions: Array<{
    a: string;
    b: string;
    lineA: number;
    lineB: number;
    kind: ContradictionKind;
  }>;
  decisions: string[];
  warnings: string[];
  pressure: PressureSignature;
  interpreterTrace: string[];
}

// ---------- Galileo (structure) --------------------------------------------

function splitSentences(text: string): string[] {
  const t = text.trim();
  if (!t) return [];
  // Protect common abbreviations from being treated as sentence ends.
  const guarded = t.replace(
    /\b(Mr|Mrs|Ms|Dr|Sr|Jr|St|Mt|U\.S|U\.K|e\.g|i\.e|etc|vs)\./g,
    "$1<DOT>"
  );
  const parts = guarded.match(/[^.!?\n]+[.!?]+|[^.!?\n]+$/g) || [t];
  return parts.map((s) => s.replace(/<DOT>/g, ".").trim()).filter(Boolean);
}

function splitParagraphs(text: string): string[][] {
  const paras = text.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  return paras.map(splitSentences);
}

function findHeadings(text: string): string[] {
  const out: string[] = [];
  for (const line of text.split(/\n/)) {
    const t = line.trim();
    if (!t) continue;
    if (/^#{1,6}\s+/.test(t)) {
      out.push(t.replace(/^#{1,6}\s+/, ""));
      continue;
    }
    // ALL-CAPS short line without terminal punctuation = heading.
    if (
      t.length <= 60 &&
      t === t.toUpperCase() &&
      /[A-Z]/.test(t) &&
      !/[.?!]$/.test(t)
    ) {
      out.push(t);
    }
  }
  return out;
}

function findBullets(text: string): string[] {
  return text
    .split(/\n/)
    .filter((line) => /^\s*(?:[-*•]|\d+[.)])\s+\S/.test(line))
    .map((s) => s.trim());
}

function findCodeBlocks(text: string): string[] {
  const blocks: string[] = [];
  const re = /```[\w-]*\n?([\s\S]*?)```/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) blocks.push(m[1].trim());
  return blocks;
}

function findQuotes(text: string): string[] {
  return text
    .split(/\n/)
    .filter((line) => /^\s*>\s+\S/.test(line))
    .map((s) => s.replace(/^\s*>\s+/, "").trim());
}

export function runGalileo(
  raw: string
): Pick<ClarityObject, "source" | "structure"> {
  return {
    source: raw,
    structure: {
      sentences: splitSentences(raw),
      paragraphs: splitParagraphs(raw),
      headings: findHeadings(raw),
      bullets: findBullets(raw),
      codeBlocks: findCodeBlocks(raw),
      quotes: findQuotes(raw),
    },
  };
}

// ---------- Tizzy (tone strip) ---------------------------------------------

const HEDGES: RegExp[] = [
  // first-person hedges
  /\bI think\b/gi,
  /\bI believe\b/gi,
  /\bI feel\b/gi,
  /\bI would say\b/gi,
  /\bI guess\b/gi,
  /\bI suppose\b/gi,
  // qualifiers
  /\bin my opinion\b/gi,
  /\bif you ask me\b/gi,
  /\bto be honest\b/gi,
  /\bif I'm honest\b/gi,
  // social filler
  /\byou know\b/gi,
  /\blike,\s*/gi,
  // approximation
  /\bit seems(?: like)?\b/gi,
  /\bit appears(?: that)?\b/gi,
  /\bmight be\b/gi,
  /\bcould be\b/gi,
  /\bmay be\b/gi,
  /\bperhaps\b/gi,
  /\bmaybe\b/gi,
  /\bpossibly\b/gi,
  /\bprobably\b/gi,
  /\bkind of\b/gi,
  /\bsort of\b/gi,
  /\ba bit\b/gi,
  // intensifiers / softeners
  /\bbasically\b/gi,
  /\bliterally\b/gi,
  /\bessentially\b/gi,
  /\bhonestly\b/gi,
  /\bactually\b/gi,
  /\bfrankly\b/gi,
  /\bquite\b/gi,
  /\bsomewhat\b/gi,
  /\bfairly\b/gi,
  /\bpretty\b/gi,
  /\bjust\b/gi,
  /\breally\b/gi,
  /\bvery\b/gi,
  /\bobviously\b/gi,
  /\bclearly\b/gi,
  /\bof course\b/gi,
];

const FILLER_INTROS =
  /^\s*(?:so|now|well|anyway|look|listen|see|right|okay|ok|alright)\s*[,.]?\s+/gim;

export function runTizzy(
  c: Pick<ClarityObject, "source" | "structure">
): Pick<ClarityObject, "toneStripped"> {
  let stripped = c.source;
  for (const re of HEDGES) stripped = stripped.replace(re, "");
  stripped = stripped.replace(FILLER_INTROS, "");
  // Tidy gaps left by removed words.
  stripped = stripped
    .replace(/\s{2,}/g, " ")
    .replace(/\s+([.,!?;:])/g, "$1")
    .replace(/([(\[{])\s+/g, "$1")
    .replace(/\s*\n\s*/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  return { toneStripped: stripped };
}

function countHedgeMatches(text: string): number {
  let n = 0;
  for (const re of HEDGES) {
    const flagless = new RegExp(re.source, "gi");
    n += (text.match(flagless) || []).length;
  }
  return n;
}

// ---------- Markov (meaning) -----------------------------------------------

const DECISION_PATTERNS: Array<{ re: RegExp; group: number }> = [
  {
    re: /^\s*(?:decide|decided to|choose|chose|go with|pick|use|do|select|prefer|opt for)\b[:,]?\s*(.+?)[.!?]?$/i,
    group: 1,
  },
  {
    re: /^\s*(?:decision|verdict|conclusion|the answer|the choice|the right move)\b\s*[:.]?\s*(.+?)[.!?]?$/i,
    group: 1,
  },
  {
    re: /\b(?:we|I|you)\s+(?:will|should|need to|are going to|must)\s+(.+?)[.!?]/i,
    group: 1,
  },
];

const IMPERATIVE_VERBS = [
  "use", "pick", "go", "do", "select", "choose", "avoid", "switch",
  "start", "stop", "continue", "try", "add", "remove", "keep",
  "enable", "disable", "install", "set", "configure", "wire",
  "replace", "update", "delete", "create", "submit", "proceed",
];
const IMPERATIVE_RE = new RegExp(
  `^\\s*(?:${IMPERATIVE_VERBS.join("|")})\\b\\s+(.+?)[.!?]?$`,
  "i"
);

const WARN_KEYWORDS =
  /\b(warning|caution|danger|risk|avoid|do not|don't|never)\b/i;

const URGENCY =
  /\b(must|now|immediately|asap|urgent|critical|right away|hurry|deadline|stat)\b/gi;

const ANTONYMS: ReadonlyArray<readonly [string, string]> = [
  ["true", "false"],
  ["yes", "no"],
  ["can", "cannot"],
  ["can", "can't"],
  ["will", "won't"],
  ["should", "shouldn't"],
  ["must", "must not"],
  ["always", "never"],
  ["safe", "dangerous"],
  ["allowed", "forbidden"],
  ["required", "optional"],
  ["cheap", "expensive"],
  ["simple", "complex"],
  ["fast", "slow"],
  ["high", "low"],
  ["good", "bad"],
  ["right", "wrong"],
];

function extractDecision(sentence: string): string | null {
  for (const { re, group } of DECISION_PATTERNS) {
    const m = re.exec(sentence);
    if (m && m[group]) {
      return m[group].trim().replace(/[.!?]+$/, "").trim();
    }
  }
  if (IMPERATIVE_RE.test(sentence)) {
    return sentence.trim().replace(/[.!?]+$/, "").trim();
  }
  return null;
}

function findContradictions(
  sentences: string[]
): ClarityObject["contradictions"] {
  const out: ClarityObject["contradictions"] = [];

  for (let i = 0; i < sentences.length; i++) {
    for (let j = i + 1; j < sentences.length; j++) {
      const a = sentences[i].toLowerCase();
      const b = sentences[j].toLowerCase();

      // 1. Direct negation: "X is Y" vs "X is not Y"
      const posA = /(\w{3,})\s+is\s+(\w+)/.exec(a);
      const negA = /(\w{3,})\s+is\s+not\s+(\w+)/.exec(a);
      const posB = /(\w{3,})\s+is\s+(\w+)/.exec(b);
      const negB = /(\w{3,})\s+is\s+not\s+(\w+)/.exec(b);
      if (posA && negB && posA[1] === negB[1] && posA[2] === negB[2]) {
        out.push({ a: sentences[i], b: sentences[j], lineA: i, lineB: j, kind: "negation" });
        continue;
      }
      if (negA && posB && negA[1] === posB[1] && negA[2] === posB[2]) {
        out.push({ a: sentences[i], b: sentences[j], lineA: i, lineB: j, kind: "negation" });
        continue;
      }

      // 2. Antonym: same subject, opposite predicates from the table.
      const subA = /^(?:the |a |an )?(\w{3,})\s+(?:is|are|was|were)\s+(\w+)/i.exec(sentences[i]);
      const subB = /^(?:the |a |an )?(\w{3,})\s+(?:is|are|was|were)\s+(\w+)/i.exec(sentences[j]);
      if (subA && subB && subA[1].toLowerCase() === subB[1].toLowerCase()) {
        const x = subA[2].toLowerCase();
        const y = subB[2].toLowerCase();
        let antonymHit = false;
        for (const [p, q] of ANTONYMS) {
          if ((x === p && y === q) || (x === q && y === p)) {
            antonymHit = true;
            break;
          }
        }
        if (antonymHit) {
          out.push({ a: sentences[i], b: sentences[j], lineA: i, lineB: j, kind: "antonym" });
          continue;
        }
      }

      // 3. Modal conflict: "X should Y" vs "X should not Y"
      const modA = /\b(should|must|can|will|do)\s+(\w+)/i.exec(a);
      const modBNeg = /\b(should|must|can|will|do)\s+not\s+(\w+)/i.exec(b);
      const modANeg = /\b(should|must|can|will|do)\s+not\s+(\w+)/i.exec(a);
      const modB = /\b(should|must|can|will|do)\s+(\w+)/i.exec(b);
      if (modA && modBNeg && modA[1] === modBNeg[1] && modA[2] === modBNeg[2]) {
        out.push({ a: sentences[i], b: sentences[j], lineA: i, lineB: j, kind: "modal" });
        continue;
      }
      if (modANeg && modB && modANeg[1] === modB[1] && modANeg[2] === modB[2]) {
        out.push({ a: sentences[i], b: sentences[j], lineA: i, lineB: j, kind: "modal" });
      }
    }
  }

  // Dedupe.
  const seen = new Set<string>();
  return out.filter((c) => {
    const k = `${c.lineA}-${c.lineB}-${c.kind}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

function computePressure(
  source: string,
  sentences: string[],
  contradictionCount: number
): PressureSignature {
  const sentenceCount = sentences.length;
  const urgencyWords = (source.match(URGENCY) || []).length;
  const imperatives = sentences.filter((s) => IMPERATIVE_RE.test(s)).length;
  const hedgeMatches = countHedgeMatches(source);
  return {
    sentenceCount,
    imperatives,
    urgencyWords,
    contradictions: contradictionCount,
    hedgeRatio:
      sentenceCount > 0
        ? Math.round((hedgeMatches / sentenceCount) * 100) / 100
        : 0,
  };
}

export function runMarkov(
  c: Pick<ClarityObject, "source" | "structure" | "toneStripped">
): Pick<ClarityObject, "contradictions" | "decisions" | "warnings" | "pressure"> {
  const sentences = c.structure.sentences;
  const decisions: string[] = [];
  const warnings: string[] = [];

  for (const s of sentences) {
    const d = extractDecision(s);
    if (d) decisions.push(d);
    if (WARN_KEYWORDS.test(s)) warnings.push(s.trim());
  }

  const contradictions = findContradictions(sentences);
  const pressure = computePressure(c.source, sentences, contradictions.length);

  return { contradictions, decisions, warnings, pressure };
}

// ---------- Pipeline -------------------------------------------------------

export async function runLangbridg(raw: string): Promise<ClarityObject> {
  const galileo = runGalileo(raw);
  const tizzy = runTizzy(galileo);
  const markov = runMarkov({ ...galileo, ...tizzy });
  return {
    ...galileo,
    ...tizzy,
    ...markov,
    interpreterTrace: ["galileo", "tizzy", "markov"],
  };
}
