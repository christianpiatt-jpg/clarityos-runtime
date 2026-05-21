// ClarityOS Mobile — Operator vault inspector (v63 / Unit 48).
//
// Phone mirror of web/src/routes/OperatorVault.tsx. Read-only.
// Single-column scroll view; JSON viewer renders as a pretty-printed
// block rather than a click-to-expand tree (collapsible trees on
// touch are awkward and the JSON is small at MVP scale).
//
// Named ``operator_vault`` (not ``vault``) to avoid colliding with
// the legacy ``phone/app/vault.tsx`` storage-layer route.
//
// v66 / Unit 70 — auth-required surface. Backend ignores the path
// operator_id since v64/Unit 66 and uses the authed identity, so the
// TextInput here was both confusing and inert. AuthGate handles
// unauthed visits with an inline CTA.

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import {
  ApiError,
  getOperatorVault,
  getUser,
  type VaultInspectorResponse,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";
import AuthGate from "../components/AuthGate";

export default function OperatorVaultScreen() {
  return (
    <AuthGate>
      <OperatorVaultScreenInner />
    </AuthGate>
  );
}

function OperatorVaultScreenInner() {
  const authedUser = getUser() || "";
  const [data, setData] = useState<VaultInspectorResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Backend ignores path operator_id and uses authed identity
      // (v64/Unit 66). We still pass authedUser for client-side log
      // clarity but server is authoritative.
      const r = await getOperatorVault(authedUser);
      setData(r);
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, [authedUser]);

  useEffect(() => {
    void fetch();
  }, [authedUser]); // eslint-disable-line react-hooks/exhaustive-deps

  const prettyJson = (() => {
    if (!data || data.vault === null) return null;
    try {
      return JSON.stringify(data.vault, null, 2);
    } catch {
      return "(non-serializable payload)";
    }
  })();

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content}>
      <View style={styles.headerPanel}>
        <Text style={styles.h1}>OPERATOR VAULT</Text>
        <Text style={styles.muted}>
          Read-only snapshot of the runtime vault — the ELINS long-arc
          state that the session loop persists between steps. Distinct
          from the legacy vault route.
        </Text>
        <Text style={styles.authedBadge}>
          Authed as <Text style={styles.authedBadgeName}>{authedUser}</Text>
        </Text>
        <Pressable
          style={({ pressed }) => [styles.btnSecondary, pressed && styles.btnPressed]}
          onPress={() => void fetch()}
          disabled={loading}
        >
          <Text style={styles.btnSecondaryText}>REFRESH</Text>
        </Pressable>
        {error ? (
          <View style={styles.banner}>
            <Text style={styles.bannerText}>{error}</Text>
          </View>
        ) : null}
      </View>

      <View style={styles.panel}>
        <View style={styles.headerRow}>
          <Text style={styles.h2}>VAULT</Text>
          <Text style={styles.metaText}>
            {data?.last_updated ? `updated ${data.last_updated}` : "never updated"}
          </Text>
        </View>
        {loading ? (
          <ActivityIndicator color={colors.accent} />
        ) : !data || data.vault === null ? (
          <Text style={styles.empty}>
            No vault recorded for this operator yet. Run a /session step
            to populate.
          </Text>
        ) : (
          <View style={styles.jsonContainer}>
            <Text style={styles.jsonText}>{prettyJson}</Text>
          </View>
        )}
      </View>
    </ScrollView>
  );
}

function formatError(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.body === "object" && e.body && "detail" in (e.body as Record<string, unknown>)) {
      const d = (e.body as Record<string, unknown>).detail;
      if (typeof d === "string") return d;
    }
    return `${e.code}: ${e.message}`;
  }
  if (e instanceof Error) return e.message;
  return String(e);
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bgDeep },
  content: { padding: space.s5 },
  headerPanel: {
    backgroundColor: colors.bgSurface,
    borderRadius: radius.lg,
    padding: space.s4,
    marginBottom: space.s3,
  },
  panel: {
    backgroundColor: colors.bgSurface,
    borderRadius: radius.lg,
    padding: space.s4,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: space.s3,
  },
  h1: { color: colors.textPrimary, fontSize: 18, fontWeight: "700" },
  h2: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },
  muted: { color: colors.textSecondary, fontSize: 13, marginTop: 4 },
  authedBadge: {
    color: colors.textSecondary,
    fontSize: 11,
    marginTop: space.s3,
  },
  authedBadgeName: {
    color: colors.textPrimary,
    fontFamily: "monospace",
  },
  btnSecondary: {
    marginTop: space.s3,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderColor: colors.textSecondary,
    borderWidth: 1,
    borderRadius: radius.sm,
    alignSelf: "flex-start",
  },
  btnPressed: { opacity: 0.6 },
  btnSecondaryText: { color: colors.textPrimary, fontSize: 12, fontWeight: "600" },
  banner: {
    marginTop: space.s3,
    padding: 8,
    backgroundColor: "rgba(239,68,68,0.12)",
    borderRadius: radius.sm,
  },
  bannerText: { color: "#ef4444", fontSize: 13 },
  empty: { color: colors.textSecondary, fontStyle: "italic" },
  metaText: { color: colors.textSecondary, fontFamily: "monospace", fontSize: 11 },
  jsonContainer: {
    backgroundColor: colors.bgDeep,
    padding: 8,
    borderRadius: radius.sm,
  },
  jsonText: {
    color: colors.textPrimary,
    fontFamily: "monospace",
    fontSize: 11,
  },
});
