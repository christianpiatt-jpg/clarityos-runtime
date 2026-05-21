// ClarityOS Mobile — Operator session history (v63 / Unit 47).
//
// Phone mirror of web/src/routes/SessionHistory.tsx. Read-only.
// Reflowed for a tall single-column scroll view: session list on
// top, expanding into the selected detail underneath. No layout
// columns — tap to switch between list-mode and detail-mode.
//
// v66 / Unit 70 — auth-required surface. The operator identity is
// the authed user (Unit 68 made the backend list endpoint authed),
// so the legacy operator_id TextInput is removed. AuthGate handles
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
  getSessionDetail,
  getUser,
  listOperatorSessions,
  type SessionDetailResponse,
  type SessionSummary,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";
import AuthGate from "../components/AuthGate";

export default function OperatorSessionHistoryScreen() {
  return (
    <AuthGate>
      <OperatorSessionHistoryScreenInner />
    </AuthGate>
  );
}

function OperatorSessionHistoryScreenInner() {
  const authedUser = getUser() || "";
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SessionDetailResponse | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchList = useCallback(async () => {
    setLoadingList(true);
    setError(null);
    try {
      // Backend ignores the path argument and uses the authed identity
      // (v64/Unit 66). We still pass authedUser for client-side log
      // clarity but server is authoritative.
      const r = await listOperatorSessions(authedUser);
      setSessions(r.sessions);
      if (r.sessions.length > 0 && selectedId === null) {
        setSelectedId(r.sessions[0].session_id);
      }
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setLoadingList(false);
    }
  }, [authedUser, selectedId]);

  useEffect(() => {
    void fetchList();
  }, [authedUser]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    (async () => {
      setLoadingDetail(true);
      try {
        const r = await getSessionDetail(selectedId);
        if (!cancelled) setDetail(r);
      } catch (e: unknown) {
        if (!cancelled) setError(formatError(e));
      } finally {
        if (!cancelled) setLoadingDetail(false);
      }
    })();
    return () => { cancelled = true; };
  }, [selectedId]);

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content}>
      <View style={styles.headerPanel}>
        <Text style={styles.h1}>SESSION HISTORY</Text>
        <Text style={styles.muted}>
          Read-only inspector over past operator sessions.
        </Text>
        <Text style={styles.authedBadge}>
          Authed as <Text style={styles.authedBadgeName}>{authedUser}</Text>
        </Text>
        <Pressable
          style={({ pressed }) => [styles.btnSecondary, pressed && styles.btnPressed]}
          onPress={() => void fetchList()}
          disabled={loadingList}
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
        <Text style={styles.h2}>SESSIONS</Text>
        {loadingList && !sessions ? (
          <ActivityIndicator color={colors.accent} />
        ) : sessions && sessions.length === 0 ? (
          <Text style={styles.empty}>No sessions for this operator.</Text>
        ) : (
          (sessions || []).map((s) => {
            const isSelected = s.session_id === selectedId;
            return (
              <Pressable
                key={s.session_id}
                onPress={() => setSelectedId(s.session_id)}
                style={[
                  styles.listRow,
                  isSelected && styles.listRowSelected,
                ]}
              >
                <Text style={styles.mono}>{s.session_id}</Text>
                <Text style={styles.metaText}>
                  {s.history_len} step(s) · {s.timestamp || "no activity"}
                </Text>
              </Pressable>
            );
          })
        )}
      </View>

      <View style={styles.panel}>
        <Text style={styles.h2}>DETAIL</Text>
        {!selectedId ? (
          <Text style={styles.empty}>Tap a session above.</Text>
        ) : loadingDetail ? (
          <ActivityIndicator color={colors.accent} />
        ) : !detail ? (
          <Text style={styles.empty}>No detail available.</Text>
        ) : (
          <SessionDetailView detail={detail} />
        )}
      </View>
    </ScrollView>
  );
}

function SessionDetailView({ detail }: { detail: SessionDetailResponse }) {
  const state = detail.session_state;
  return (
    <View>
      <View style={styles.kv}>
        <Text style={styles.kvKey}>session_id</Text>
        <Text style={styles.mono}>{state.session_id}</Text>
        <Text style={styles.kvKey}>history</Text>
        <Text>{state.history.length} step(s)</Text>
      </View>

      <Text style={[styles.h2, { marginTop: space.s3 }]}>STEPS</Text>
      {state.history.length === 0 ? (
        <Text style={styles.empty}>No steps in this session yet.</Text>
      ) : (
        state.history.map((entry, i) => (
          <View
            key={`${entry.timestamp}-${i}`}
            style={[
              styles.stepRow,
              { borderLeftColor: decisionColor(entry.runtime_decision) },
            ]}
          >
            <Text style={styles.metaText}>
              #{i + 1} · {entry.timestamp} · intent={entry.intent_type} · engine={entry.engine}
            </Text>
            <Text
              style={[
                styles.decisionPill,
                { color: decisionColor(entry.runtime_decision) },
              ]}
            >
              {entry.runtime_decision.toUpperCase()}
            </Text>
            <Text style={styles.bodyText}>{entry.text}</Text>
          </View>
        ))
      )}
    </View>
  );
}

function decisionColor(decision: string): string {
  if (decision === "block") return "#ef4444";
  if (decision === "warn")  return "#f59e0b";
  return "#10b981";
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
    marginBottom: space.s3,
  },
  h1: { color: colors.textPrimary, fontSize: 18, fontWeight: "700" },
  h2: { color: colors.textPrimary, fontSize: 14, fontWeight: "600", marginBottom: space.s3 },
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
  listRow: {
    paddingVertical: 8,
    paddingHorizontal: 4,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
  },
  listRowSelected: {
    backgroundColor: "rgba(255,255,255,0.04)",
  },
  mono: {
    color: colors.textPrimary,
    fontFamily: "monospace",
    fontSize: 13,
  },
  metaText: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
  kv: {
    backgroundColor: colors.bgDeep,
    padding: 8,
    borderRadius: radius.sm,
  },
  kvKey: { color: colors.textSecondary, fontSize: 11, marginTop: 4 },
  stepRow: {
    padding: 10,
    marginBottom: 8,
    backgroundColor: colors.bgDeep,
    borderLeftWidth: 3,
    borderRadius: radius.sm,
  },
  decisionPill: {
    fontFamily: "monospace",
    fontSize: 11,
    fontWeight: "700",
    marginVertical: 4,
  },
  bodyText: { color: colors.textPrimary, fontSize: 13 },
});
