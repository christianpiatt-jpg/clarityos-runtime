import { router, Stack } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import * as SystemUI from "expo-system-ui";
import { colors } from "../lib/theme";
import {
  getSession,
  loadSession,
  probeBackend,
  refreshProfile,
  type BackendStatus,
} from "../lib/api";
import { getResumeOptions } from "../lib/continuity";

/**
 * Startup sequence (best-effort; nothing here blocks the app from rendering):
 *   1. Load cached session token from AsyncStorage.
 *   2. Probe /health to check backend reachability (with 2-attempt retry).
 *   3. If a session exists, call /me to populate the in-memory profile
 *      (cohort + operator_id). On 401/403 the profile cache + storage
 *      session are cleared automatically by refreshProfile().
 *   4. Read continuity options. If any, defer-push /continuity so the
 *      initial route renders first.
 *
 * Any single step failing leaves the app usable — the screens have their
 * own retry / sign-in paths.
 */
export default function RootLayout() {
  const [ready, setReady] = useState(false);
  // Backend status is exposed via a ref-style global so screens can read
  // it without prop-drilling. Today only the layout consumes it.
  const [, setBackendStatus] = useState<BackendStatus | null>(null);

  useEffect(() => {
    SystemUI.setBackgroundColorAsync(colors.bgDeep).catch(() => {});

    let cancelled = false;
    (async () => {
      // 1. Cached session
      try {
        await loadSession();
      } catch {
        // AsyncStorage hiccup — proceed; screens treat as signed-out.
      }

      // 2. Backend probe (non-blocking; failure shows up as banners later)
      let status: BackendStatus | null = null;
      try {
        status = await probeBackend();
        if (!cancelled) setBackendStatus(status);
      } catch {
        // probeBackend already swallows errors and returns reachable=false;
        // this catch is paranoia.
      }

      // 3. /me refresh (only if we have a session AND the backend looks alive)
      if (getSession() && status?.reachable) {
        try {
          await refreshProfile();
        } catch {
          // refreshProfile handles 401/403 internally — nothing to do here.
        }
      }

      // 4. Continuity check
      let resumeOpts: Awaited<ReturnType<typeof getResumeOptions>> = [];
      try {
        resumeOpts = await getResumeOptions();
      } catch {
        // Local-only read; should never throw, but be defensive.
      }

      if (cancelled) return;
      setReady(true);
      if (resumeOpts.length > 0) {
        // Defer one tick so the initial route renders before we push.
        setTimeout(() => router.push("/continuity"), 0);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  if (!ready) {
    return (
      <View
        style={{
          flex: 1,
          backgroundColor: colors.bgDeep,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: colors.bgDeep },
          headerTintColor: colors.textPrimary,
          headerTitleStyle: { color: colors.textPrimary, fontWeight: "600" },
          contentStyle: { backgroundColor: colors.bgDeep },
        }}
      >
        <Stack.Screen name="index" options={{ title: "ClarityOS" }} />
        <Stack.Screen name="login" options={{ title: "Sign in" }} />
        <Stack.Screen name="session/[id]" options={{ title: "Session" }} />
        <Stack.Screen name="settings" options={{ title: "Settings" }} />
        <Stack.Screen name="vault" options={{ title: "Vault" }} />
        <Stack.Screen name="chat" options={{ title: "Chat" }} />
        <Stack.Screen name="copy" options={{ title: "Copy" }} />
        <Stack.Screen name="continuity" options={{ title: "Continuity" }} />
        <Stack.Screen name="ingest" options={{ title: "Ingest" }} />
        <Stack.Screen name="invite/[token]" options={{ title: "Invite" }} />
        <Stack.Screen name="forecast" options={{ title: "Forecast" }} />
        <Stack.Screen name="elins_inspector" options={{ title: "ELINS inspector" }} />
        <Stack.Screen name="regional" options={{ title: "Regional ELINS" }} />
        <Stack.Screen name="regional_detail" options={{ title: "Regional detail" }} />
        <Stack.Screen name="regional_forecast" options={{ title: "Regional forecast" }} />
        <Stack.Screen name="macro_runs" options={{ title: "Macro-ELINS" }} />
        <Stack.Screen name="macro_run_detail" options={{ title: "Macro run" }} />
        <Stack.Screen name="macro_scheduler_config" options={{ title: "Scheduler config" }} />
        <Stack.Screen name="entities" options={{ title: "Entity graph" }} />
        <Stack.Screen name="entity_detail" options={{ title: "Entity" }} />
        <Stack.Screen name="entity_timeseries" options={{ title: "Entity timeseries" }} />
        <Stack.Screen name="dashboard" options={{ title: "ELINS dashboard" }} />
        <Stack.Screen name="dashboard_global" options={{ title: "Global" }} />
        <Stack.Screen name="dashboard_regional" options={{ title: "Regional" }} />
        <Stack.Screen name="dashboard_entities" options={{ title: "Entities" }} />
        <Stack.Screen name="operator_profile" options={{ title: "My profile" }} />
        <Stack.Screen name="operator_timeline" options={{ title: "Timeline" }} />
        <Stack.Screen name="founder_analytics" options={{ title: "Analytics" }} />
        <Stack.Screen name="model_preferences" options={{ title: "Model preferences" }} />
        <Stack.Screen name="local_model" options={{ title: "Local model" }} />
        <Stack.Screen name="memory_vault" options={{ title: "Memory Vault" }} />
        <Stack.Screen name="memory_vault_embeddings" options={{ title: "Vault embeddings" }} />
        <Stack.Screen name="threads" options={{ title: "Threads" }} />
        <Stack.Screen name="thread/[id]" options={{ title: "Thread" }} />
        <Stack.Screen name="operator_session" options={{ title: "Operator session" }} />
        {/* v63 / Units 47 + 48 — Session history + vault inspector. */}
        <Stack.Screen name="operator_session_history" options={{ title: "Session history" }} />
        <Stack.Screen name="operator_vault" options={{ title: "Operator vault" }} />
        {/* v64 / Unit 67 — Model preferences. */}
        <Stack.Screen name="operator_model_preferences" options={{ title: "Model preferences" }} />
        {/* v69 / Unit 74 — EL/INS reasoning-stability operator. */}
        <Stack.Screen name="el_ins" options={{ title: "EL/INS" }} />
        {/* v70 / Unit 77 — EL/INS macro dashboard. */}
        <Stack.Screen name="el_ins_dashboard" options={{ title: "EL/INS Dashboard" }} />
        {/* v71 / Unit 78 — EL/INS export. */}
        <Stack.Screen name="el_ins_export" options={{ title: "EL/INS Export" }} />
        {/* v72 / Units 80+81 — anomalies + roll-up. */}
        <Stack.Screen name="el_ins_anomalies" options={{ title: "EL/INS Anomalies" }} />
        <Stack.Screen name="el_ins_rollup" options={{ title: "EL/INS Roll-Up" }} />
        {/* v73 / Units 82+83 — operator + org timeline. */}
        <Stack.Screen name="timeline" options={{ title: "Timeline" }} />
        <Stack.Screen name="org_timeline" options={{ title: "Org Timeline" }} />
        {/* v80 — Regression-First packet runner. */}
        <Stack.Screen name="regression_first" options={{ title: "Regression First" }} />
        {/* Card 40 — Engine V1 operator console (Phase-1 diagnostic). */}
        <Stack.Screen name="operator_console" options={{ title: "Operator Console" }} />
      </Stack>
    </>
  );
}
