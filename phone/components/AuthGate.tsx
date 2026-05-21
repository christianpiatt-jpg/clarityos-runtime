// AuthGate — phone-side equivalent of web's RequireAuth inline CTA.
//
// v66 / Unit 70 — gates operator-scoped screens. When the user has no
// session, renders an inline "Sign in required" CTA with a button that
// routes to /login. When authed, renders children unchanged.
//
// Design choice: inline CTA instead of router.replace so the user
// sees what surface they're being asked to authenticate for and can
// back out cleanly. Matches the web RequireAuth contract.

import { ReactNode } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { getUser } from "../lib/api";
import { colors, radius, space } from "../lib/theme";

interface Props {
  children: ReactNode;
  /** Override default message body. */
  message?: string;
}

export default function AuthGate({ children, message }: Props) {
  const user = getUser();
  if (user) return <>{children}</>;
  return (
    <View style={styles.root}>
      <View style={styles.card}>
        <Text style={styles.h1}>Sign in required</Text>
        <Text style={styles.body}>
          {message ?? "You need to sign in to start or resume sessions."}
        </Text>
        <Pressable
          style={({ pressed }) => [styles.cta, pressed && styles.ctaPressed]}
          onPress={() => router.push("/login")}
          accessibilityRole="button"
          accessibilityLabel="Sign in"
        >
          <Text style={styles.ctaLabel}>SIGN IN</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.bgDeep,
    padding: space.s5,
    justifyContent: "center",
  },
  card: {
    backgroundColor: colors.bgSurface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: space.s5,
  },
  h1: {
    color: colors.textPrimary,
    fontSize: 18,
    fontWeight: "700",
    marginBottom: space.s2,
  },
  body: {
    color: colors.textSecondary,
    fontSize: 14,
    lineHeight: 20,
    marginBottom: space.s4,
  },
  cta: {
    backgroundColor: colors.accent,
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: radius.pill,
    alignSelf: "flex-start",
  },
  ctaPressed: { opacity: 0.8 },
  ctaLabel: { color: "#04121b", fontWeight: "700", letterSpacing: 0.5 },
});
