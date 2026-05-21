import { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { router } from "expo-router";
import Orb from "../components/Orb";
import { colors, radius, space } from "../lib/theme";
import * as api from "../lib/api";

type Mode = "login" | "register";

export default function LoginScreen() {
  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setError(null);
    if (!username.trim() || !password) {
      setError("Username and password are required");
      return;
    }
    if (mode === "register" && password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setBusy(true);
    try {
      if (mode === "login") await api.login(username.trim(), password);
      else await api.register(username.trim(), password);
      router.replace("/");
    } catch (e: any) {
      setError(e?.message || "Sign in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <View style={{ alignItems: "center", marginVertical: space.s5 }}>
          <Orb size={140} />
        </View>

        <View style={styles.card}>
          <View style={styles.tabs}>
            <Pressable onPress={() => setMode("login")} style={[styles.tab, mode === "login" && styles.tabActive]}>
              <Text style={[styles.tabLabel, mode === "login" && styles.tabLabelActive]}>Sign in</Text>
            </Pressable>
            <Pressable onPress={() => setMode("register")} style={[styles.tab, mode === "register" && styles.tabActive]}>
              <Text style={[styles.tabLabel, mode === "register" && styles.tabLabelActive]}>Create account</Text>
            </Pressable>
          </View>

          {error && <Text style={styles.error}>{error}</Text>}

          <Text style={styles.label}>Username</Text>
          <TextInput
            value={username}
            onChangeText={setUsername}
            autoCapitalize="none"
            autoCorrect={false}
            placeholder=""
            placeholderTextColor={colors.textTertiary}
            style={styles.input}
          />

          <Text style={styles.label}>Password</Text>
          <TextInput
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            placeholderTextColor={colors.textTertiary}
            style={styles.input}
          />

          <Pressable onPress={submit} style={[styles.cta, busy && { opacity: 0.6 }]} disabled={busy}>
            {busy ? <ActivityIndicator color="#04121b" /> : <Text style={styles.ctaLabel}>{mode === "login" ? "Sign in" : "Create account"}</Text>}
          </Pressable>
        </View>

        <Pressable onPress={() => router.push("/settings")} style={{ alignSelf: "center", padding: space.s4 }}>
          <Text style={{ color: colors.textTertiary, fontSize: 13 }}>Backend: configure in Settings</Text>
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { padding: space.s5, paddingTop: space.s7 },
  card: {
    backgroundColor: colors.bgSurface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: space.s5,
  },
  tabs: { flexDirection: "row", marginHorizontal: -space.s5, marginTop: -space.s5, marginBottom: space.s5, borderBottomWidth: 1, borderBottomColor: colors.border },
  tab: { flex: 1, paddingVertical: space.s4, alignItems: "center", borderBottomWidth: 2, borderBottomColor: "transparent" },
  tabActive: { borderBottomColor: colors.accent },
  tabLabel: { color: colors.textSecondary, fontSize: 14 },
  tabLabelActive: { color: colors.textPrimary, fontWeight: "600" },
  label: { color: colors.textSecondary, fontSize: 13, marginBottom: space.s2, marginTop: space.s3 },
  input: {
    backgroundColor: colors.bgDeep,
    borderColor: colors.borderStrong,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: colors.textPrimary,
    fontSize: 15,
  },
  cta: {
    backgroundColor: colors.accent,
    paddingVertical: 14,
    borderRadius: radius.pill,
    alignItems: "center",
    marginTop: space.s5,
  },
  ctaLabel: { color: "#04121b", fontWeight: "700", fontSize: 15 },
  error: { color: colors.danger, fontSize: 13, marginBottom: space.s3 },
});
