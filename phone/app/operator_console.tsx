// Card 40 — Operator Console (phone screen).
//
// Phase-1 minimal diagnostic panel mirroring web's OperatorConsole
// and desktop's OperatorConsoleShell. React Native primitives only
// (no DOM): TextInput multiline / Pressable / ScrollView / Text.
//
// Body: textarea-equivalent JSON input → LOAD → 4 result panes
// (lineage map / hydraulic evolution / system overlay / regression
// diff). All wiring through the Card 39 EngineV1OperatorAPI.

import { useMemo, useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  createEngineV1OperatorAPI,
  type EngineV1MultiRunContext,
} from "../lib/api";

const PLACEHOLDER = `{
  "runs": []
}`;

export default function OperatorConsoleScreen() {
  const api = useMemo(() => createEngineV1OperatorAPI(), []);

  const [jsonText,  setJsonText]  = useState<string>(PLACEHOLDER);
  const [context,   setContext]   = useState<EngineV1MultiRunContext | null>(null);
  const [parseErr,  setParseErr]  = useState<string | null>(null);

  const [fromIndexText, setFromIndexText] = useState<string>("0");
  const [toIndexText,   setToIndexText]   = useState<string>("1");

  const fromIndex = Number(fromIndexText);
  const toIndex   = Number(toIndexText);

  function handleLoad() {
    setParseErr(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(jsonText);
    } catch (e) {
      setParseErr(`JSON parse error: ${(e as Error).message}`);
      setContext(null);
      return;
    }
    if (
      !parsed ||
      typeof parsed !== "object" ||
      !Array.isArray((parsed as { runs?: unknown }).runs)
    ) {
      setParseErr('Expected an object with a "runs" array.');
      setContext(null);
      return;
    }
    setContext(parsed as EngineV1MultiRunContext);
  }

  const lineageMap = useMemo(
    () => (context ? api.buildLineageMap(context) : null),
    [api, context],
  );
  const hydraulicEvolution = useMemo(
    () => (lineageMap ? api.buildHydraulicEvolution(lineageMap) : null),
    [api, lineageMap],
  );
  const systemOverlay = useMemo(
    () => (context ? api.buildSystemOverlay(context) : null),
    [api, context],
  );
  const regressionDiff = useMemo(() => {
    if (!systemOverlay) return null;
    const runCount = systemOverlay.hydraulicEvolution.perRun.length;
    if (
      !Number.isInteger(fromIndex) || fromIndex < 0 || fromIndex >= runCount ||
      !Number.isInteger(toIndex)   || toIndex   < 0 || toIndex   >= runCount
    ) {
      return null;
    }
    try {
      return api.computeSystemRegression(systemOverlay, fromIndex, toIndex);
    } catch (e) {
      return { error: (e as Error).message };
    }
  }, [api, systemOverlay, fromIndex, toIndex]);

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
      <Text style={styles.h1}>Operator Console</Text>
      <Text>Engine V1 — Phase-1 diagnostic panel.</Text>

      <View style={styles.section}>
        <Text style={styles.h2}>Input</Text>
        <TextInput
          value={jsonText}
          onChangeText={setJsonText}
          multiline
          numberOfLines={12}
          style={styles.input}
          autoCorrect={false}
          autoCapitalize="none"
        />
        <Pressable onPress={handleLoad} style={styles.button}>
          <Text>LOAD</Text>
        </Pressable>
        {parseErr ? <Text style={styles.error}>{parseErr}</Text> : null}
      </View>

      <View style={styles.section}>
        <Text style={styles.h2}>Lineage Map</Text>
        <Text style={styles.pre}>
          {lineageMap ? JSON.stringify(lineageMap, null, 2) : "(no context loaded)"}
        </Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.h2}>Hydraulic Evolution</Text>
        <Text style={styles.pre}>
          {hydraulicEvolution
            ? JSON.stringify(hydraulicEvolution, null, 2)
            : "(no context loaded)"}
        </Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.h2}>System Overlay</Text>
        <Text style={styles.pre}>
          {systemOverlay ? JSON.stringify(systemOverlay, null, 2) : "(no context loaded)"}
        </Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.h2}>System Regression Diff</Text>
        <View style={styles.row}>
          <Text>fromIndex </Text>
          <TextInput
            value={fromIndexText}
            onChangeText={setFromIndexText}
            keyboardType="number-pad"
            style={styles.indexInput}
          />
          <Text>  toIndex </Text>
          <TextInput
            value={toIndexText}
            onChangeText={setToIndexText}
            keyboardType="number-pad"
            style={styles.indexInput}
          />
        </View>
        <Text style={styles.pre}>
          {regressionDiff
            ? JSON.stringify(regressionDiff, null, 2)
            : "(load a context with at least 2 runs and valid indices)"}
        </Text>
      </View>
    </ScrollView>
  );
}

// Minimal layout-only styles. No theme tokens, no colours beyond
// monospace + borders — keeps the spec's "zero styling" rule honest
// while staying RN-renderable (RN won't display a bare nested Text
// inside a ScrollView without at least flex defaults).
const styles = StyleSheet.create({
  scroll:        { flex: 1 },
  scrollContent: { padding: 12 },
  h1:            { fontSize: 20, fontWeight: "600", marginBottom: 4 },
  h2:            { fontSize: 16, fontWeight: "600", marginTop: 12, marginBottom: 4 },
  section:       { marginTop: 12 },
  input:         {
    borderWidth: 1,
    borderColor: "#888",
    fontFamily:  "Courier",
    minHeight:   180,
    padding:     8,
  },
  button:        {
    borderWidth: 1,
    borderColor: "#888",
    paddingVertical:   6,
    paddingHorizontal: 12,
    alignSelf:    "flex-start",
    marginTop:    8,
  },
  error:         { color: "#a00", marginTop: 8 },
  pre:           {
    fontFamily: "Courier",
    fontSize:   12,
  },
  row:           { flexDirection: "row", alignItems: "center", flexWrap: "wrap" },
  indexInput:    {
    borderWidth: 1,
    borderColor: "#888",
    padding:     4,
    minWidth:    50,
  },
});
