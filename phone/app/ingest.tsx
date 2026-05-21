// /ingest — paste a body of notes, run each through the existing pipeline
// (routeModelRequest → runLangbridg → transform → clarityPayloadFrom),
// preview the structured result, save the lot to the vault.
//
// Ordering: detected timestamps where present, synthetic "now − i min"
// otherwise, sorted reverse-chronological. Anything older than 90 days
// is filtered out before the pipeline runs.
//
// Frontend-only. Vault writes go through the existing saveNote helper;
// schema unchanged.

import { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { colors, geometry, spacing, typography } from "../lib/designSystem";
import { routeModelRequest, type ModelId } from "../lib/modelRouter";
import { runLangbridg } from "../lib/langbridg";
import { transform } from "../lib/clarity";
import { clarityPayloadFrom, saveNote, type VaultClarityPayload } from "../lib/vault";

const DEFAULT_MODEL: ModelId = "copilot";
const NINETY_DAYS_MS = 90 * 24 * 60 * 60 * 1000;
const DAY_MS = 86_400_000;

type RawEntry = {
  rawIndex: number;
  text: string;
  timestamp: number;
  isSynthetic: boolean;
};

type ProcessedEntry = {
  id: string;
  source: string;
  timestamp: number;
  isSynthetic: boolean;
  distilled: string;
  payload: VaultClarityPayload;
};

// ---------- Timestamp detection -------------------------------------------

function detectTimestamp(text: string, now: number): number | null {
  // ISO date / datetime — `2026-05-04`, `2026-05-04T13:00:00Z`
  const iso = /\b(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}:\d{2}(?::\d{2})?))?/.exec(text);
  if (iso) {
    const stamp = iso[4]
      ? `${iso[1]}-${iso[2]}-${iso[3]}T${iso[4]}`
      : `${iso[1]}-${iso[2]}-${iso[3]}T00:00:00`;
    const d = new Date(stamp);
    if (!isNaN(d.getTime())) return d.getTime();
  }

  // US date — `5/4/26`, `5/4/2026`
  const us = /\b(\d{1,2})\/(\d{1,2})\/(\d{2}|\d{4})\b/.exec(text);
  if (us) {
    const m = parseInt(us[1], 10);
    const d = parseInt(us[2], 10);
    let y = parseInt(us[3], 10);
    if (y < 100) y += 2000;
    if (m >= 1 && m <= 12 && d >= 1 && d <= 31) {
      const date = new Date(y, m - 1, d);
      if (!isNaN(date.getTime())) return date.getTime();
    }
  }

  // Month name — `May 4, 2026`, `May 4`
  const monthRe =
    /\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2})(?:,?\s+(\d{4}))?\b/i;
  const mon = monthRe.exec(text);
  if (mon) {
    const months = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"];
    const idx = months.indexOf(mon[1].toLowerCase().slice(0, 3));
    const day = parseInt(mon[2], 10);
    const year = mon[3] ? parseInt(mon[3], 10) : new Date(now).getFullYear();
    if (idx >= 0 && day >= 1 && day <= 31) {
      const date = new Date(year, idx, day);
      if (!isNaN(date.getTime())) return date.getTime();
    }
  }

  // Relative — `today`, `yesterday`, `N <unit> ago`, `last week`, `last month`
  const lower = text.toLowerCase();
  if (/\btoday\b/.test(lower)) return now;
  if (/\byesterday\b/.test(lower)) return now - DAY_MS;
  const ago = /\b(\d+)\s+(minute|hour|day|week|month)s?\s+ago\b/.exec(lower);
  if (ago) {
    const n = parseInt(ago[1], 10);
    const ms: Record<string, number> = {
      minute: 60_000,
      hour: 3_600_000,
      day: DAY_MS,
      week: 7 * DAY_MS,
      month: 30 * DAY_MS,
    };
    return now - n * (ms[ago[2]] || 0);
  }
  if (/\blast week\b/.test(lower)) return now - 7 * DAY_MS;
  if (/\blast month\b/.test(lower)) return now - 30 * DAY_MS;

  return null;
}

// ---------- Splitting ------------------------------------------------------

function splitEntries(raw: string, now: number): RawEntry[] {
  // Prefer paragraph splits (blank lines) when present — that matches how
  // operators paste multi-line notes. Fall back to single-newline split if
  // the paste has no blank lines (one entry per line).
  const hasBlankLines = /\n\s*\n/.test(raw);
  const splitRe = hasBlankLines ? /\n\s*\n+/ : /\n+/;
  const parts = raw.split(splitRe).map((p) => p.trim()).filter(Boolean);
  return parts.map((text, i) => {
    const detected = detectTimestamp(text, now);
    return {
      rawIndex: i,
      text,
      timestamp: detected ?? now - i * 60_000,
      isSynthetic: detected === null,
    };
  });
}

// ---------- Component ------------------------------------------------------

export default function IngestScreen() {
  const [raw, setRaw] = useState("");
  const [processed, setProcessed] = useState<ProcessedEntry[]>([]);
  const [skippedOld, setSkippedOld] = useState(0);
  const [pipelineErrors, setPipelineErrors] = useState<string[]>([]);
  const [processing, setProcessing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedCount, setSavedCount] = useState(0);

  async function processNotes() {
    if (processing || saving) return;
    if (!raw.trim()) return;

    setProcessing(true);
    setPipelineErrors([]);
    setSavedCount(0);

    const now = Date.now();
    const cutoff = now - NINETY_DAYS_MS;

    // 1. Split → 2. Timestamp → 3. Sort newest first → 4. 90-day cutoff
    const entries = splitEntries(raw, now)
      .sort((a, b) => b.timestamp - a.timestamp);
    const inWindow = entries.filter((e) => e.timestamp >= cutoff);
    setSkippedOld(entries.length - inWindow.length);

    // 5. Pipeline (in reverse-chronological order)
    const out: ProcessedEntry[] = [];
    const errs: string[] = [];
    for (const e of inWindow) {
      try {
        const r = await routeModelRequest(DEFAULT_MODEL, e.text);
        if (!r.ok) {
          errs.push(`[${new Date(e.timestamp).toLocaleString()}] ${r.code}: ${r.error}`);
          continue;
        }
        const clarity = await runLangbridg(r.raw);
        const distilled = transform(clarity).text;
        const payload = clarityPayloadFrom(clarity);
        out.push({
          id: `ing_${e.timestamp}_${e.rawIndex}`,
          source: e.text,
          timestamp: e.timestamp,
          isSynthetic: e.isSynthetic,
          distilled,
          payload,
        });
      } catch (err: any) {
        errs.push(`[${new Date(e.timestamp).toLocaleString()}] ${err?.message || err}`);
      }
    }

    setProcessed(out);
    setPipelineErrors(errs);
    setProcessing(false);
  }

  async function saveAll() {
    if (saving || processing || processed.length === 0) return;
    setSaving(true);
    const saveErrors: string[] = [];
    let count = 0;
    try {
      // `processed` is already sorted newest → oldest. saveNote in the same
      // loop preserves that order in the file system (filenames are
      // timestamp-derived in vault.ts, so directory listing also preserves it).
      for (const e of processed) {
        try {
          await saveNote({
            type: "note",
            content: e.distilled,
            tags: ["ingest", DEFAULT_MODEL],
            source: "ai",
            providerId: DEFAULT_MODEL,
            clarity: e.payload,
          });
          count++;
        } catch (err: any) {
          saveErrors.push(
            `[${new Date(e.timestamp).toLocaleString()}] save failed: ${err?.message || err}`
          );
        }
      }
      setSavedCount(count);
      if (saveErrors.length === 0) {
        // Clean run — clear and return to caller.
        setProcessed([]);
        setRaw("");
        setSkippedOld(0);
        setPipelineErrors([]);
        router.back();
      } else {
        // Partial run — keep state visible so the operator can decide.
        setPipelineErrors([...pipelineErrors, ...saveErrors]);
      }
    } finally {
      setSaving(false);
    }
  }

  const canProcess = !!raw.trim() && !processing && !saving;
  const canSave = processed.length > 0 && !processing && !saving;

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <View style={styles.body}>
        <Text style={[typography.label12, styles.firstLabel]}>PASTE INPUT</Text>
        <TextInput
          style={styles.textarea}
          multiline
          textAlignVertical="top"
          value={raw}
          onChangeText={setRaw}
          placeholder="Paste your notes here"
          placeholderTextColor={colors.darkGrey}
          editable={!processing && !saving}
        />

        <Pressable
          onPress={processNotes}
          disabled={!canProcess}
          style={({ pressed }) => [
            styles.primaryBtn,
            {
              backgroundColor: pressed && canProcess ? colors.cyan : "transparent",
              opacity: canProcess ? 1 : 0.5,
            },
          ]}
        >
          {({ pressed }) => (
            <Text
              style={[
                typography.label14,
                { color: pressed && canProcess ? colors.black : colors.cyan },
              ]}
            >
              {processing ? "PROCESSING…" : "PROCESS NOTES"}
            </Text>
          )}
        </Pressable>

        <Text style={[typography.label12, styles.label]}>
          PROCESSED{processed.length > 0 ? ` (${processed.length})` : ""}
          {skippedOld > 0 ? `  ·  ${skippedOld} skipped (>90 days)` : ""}
        </Text>

        <ScrollView
          style={styles.previewList}
          contentContainerStyle={styles.previewContent}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode={Platform.OS === "ios" ? "interactive" : "on-drag"}
        >
          {processed.length === 0 && !processing ? (
            <Text style={[typography.body16, styles.placeholder]}>
              No entries processed yet. Paste notes above and tap PROCESS NOTES.
            </Text>
          ) : null}

          {processed.map((entry) => (
            <PreviewCard key={entry.id} entry={entry} />
          ))}

          {pipelineErrors.length > 0 ? (
            <View style={styles.errorBlock}>
              <Text style={[typography.label12, { color: colors.red }]}>
                PIPELINE ERRORS ({pipelineErrors.length})
              </Text>
              {pipelineErrors.map((e, i) => (
                <Text key={i} style={[typography.label14, styles.errorLine]}>
                  {e}
                </Text>
              ))}
            </View>
          ) : null}
        </ScrollView>
      </View>

      <SafeAreaView edges={["bottom"]} style={styles.bottomSafe}>
        <Pressable
          onPress={saveAll}
          disabled={!canSave}
          style={({ pressed }) => [
            styles.saveBtn,
            {
              backgroundColor: pressed && canSave ? colors.cyan : "transparent",
              opacity: canSave ? 1 : 0.5,
            },
          ]}
        >
          {({ pressed }) => (
            <Text
              style={[
                typography.label14,
                { color: pressed && canSave ? colors.black : colors.cyan },
              ]}
            >
              {saving
                ? `SAVING… ${savedCount}/${processed.length}`
                : `SAVE ALL TO VAULT${processed.length ? ` (${processed.length})` : ""}`}
            </Text>
          )}
        </Pressable>
      </SafeAreaView>
    </KeyboardAvoidingView>
  );
}

// ---------- Preview card --------------------------------------------------

function PreviewCard({ entry }: { entry: ProcessedEntry }) {
  const p = entry.payload.pressure;
  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Text style={[typography.label12, { color: colors.cyan }]}>
          {new Date(entry.timestamp).toLocaleString()}
          {entry.isSynthetic ? "  ·  synthetic" : ""}
        </Text>
      </View>

      <Text style={[typography.label12, styles.cardSection]}>DISTILLED</Text>
      <Text style={typography.body16}>{entry.distilled || "(empty)"}</Text>

      {entry.payload.decisions.length > 0 ? (
        <>
          <Text style={[typography.label12, styles.cardSection]}>DECISIONS</Text>
          {entry.payload.decisions.map((d, i) => (
            <Text key={i} style={typography.body16}>
              {i + 1}. {d}
            </Text>
          ))}
        </>
      ) : null}

      {entry.payload.warnings.length > 0 ? (
        <>
          <Text style={[typography.label12, styles.cardSectionWarn]}>WARNINGS</Text>
          {entry.payload.warnings.map((w, i) => (
            <Text key={i} style={[typography.body16, { color: colors.red }]}>
              ! {w}
            </Text>
          ))}
        </>
      ) : null}

      {entry.payload.contradictions.length > 0 ? (
        <>
          <Text style={[typography.label12, styles.cardSection]}>CONTRADICTIONS</Text>
          {entry.payload.contradictions.map((c, i) => (
            <Text key={i} style={typography.body16}>
              {i + 1}. [{c.kind}] {c.a} ⟷ {c.b}
            </Text>
          ))}
        </>
      ) : null}

      <Text style={[typography.label12, styles.cardSectionMeta]}>
        PRESSURE  sentences={p.sentenceCount}  imperatives={p.imperatives}  urgency={p.urgencyWords}  hedge={p.hedgeRatio}  contradictions={p.contradictions}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.black },
  body: { flex: 1, padding: spacing.frame },
  firstLabel: { color: colors.cyan, marginBottom: spacing.blockPadding },
  label: {
    color: colors.cyan,
    marginTop: spacing.blockGap,
    marginBottom: spacing.blockPadding,
  },
  textarea: {
    flex: 1,
    minHeight: 120,
    backgroundColor: colors.deepGrey,
    borderColor: colors.neutralGrey,
    borderWidth: 1,
    borderRadius: geometry.radius0,
    paddingHorizontal: spacing.blockPadding,
    paddingVertical: spacing.blockPadding,
    color: colors.white,
    fontSize: 16,
  },
  primaryBtn: {
    paddingVertical: spacing.buttonPaddingVertical,
    borderWidth: 1,
    borderColor: colors.cyan,
    borderRadius: geometry.radius0,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.blockGap,
  },
  previewList: { flex: 1 },
  previewContent: { paddingBottom: spacing.frame },
  placeholder: { color: colors.darkGrey, paddingVertical: spacing.blockPadding },
  card: {
    backgroundColor: colors.deepGrey,
    padding: spacing.blockPadding,
    marginBottom: spacing.blockGap,
    borderWidth: 1,
    borderColor: colors.neutralGrey,
    borderRadius: geometry.radius0,
  },
  cardHeader: {
    marginBottom: spacing.blockPadding,
    paddingBottom: spacing.blockPadding,
    borderBottomWidth: 1,
    borderBottomColor: colors.neutralGrey,
  },
  cardSection: {
    color: colors.cyan,
    marginTop: spacing.blockPadding,
    marginBottom: 4,
  },
  cardSectionWarn: {
    color: colors.red,
    marginTop: spacing.blockPadding,
    marginBottom: 4,
  },
  cardSectionMeta: {
    color: colors.darkGrey,
    marginTop: spacing.blockPadding,
    marginBottom: 0,
  },
  errorBlock: {
    backgroundColor: colors.deepGrey,
    padding: spacing.blockPadding,
    borderWidth: 1,
    borderColor: colors.red,
    borderRadius: geometry.radius0,
    marginBottom: spacing.blockGap,
  },
  errorLine: { color: colors.red, marginTop: 4 },
  bottomSafe: {
    backgroundColor: colors.black,
    borderTopWidth: 1,
    borderTopColor: colors.neutralGrey,
  },
  saveBtn: {
    margin: spacing.frame,
    paddingVertical: spacing.buttonPaddingVertical,
    borderWidth: 1,
    borderColor: colors.cyan,
    borderRadius: geometry.radius0,
    alignItems: "center",
    justifyContent: "center",
  },
});
