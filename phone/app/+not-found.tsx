// Phase 6 — phone not-found surface for unmatched routes (expo-router).
import { Link, Stack } from "expo-router";
import { Text, View } from "react-native";
import { colors } from "../lib/theme";

export default function NotFoundScreen() {
  return (
    <>
      <Stack.Screen options={{ title: "Not found" }} />
      <View
        style={{
          flex: 1, backgroundColor: colors.bgDeep,
          alignItems: "center", justifyContent: "center", padding: 24,
        }}
      >
        <Text style={{ color: colors.textPrimary, fontSize: 18, fontWeight: "700", marginBottom: 8 }}>
          Screen not found
        </Text>
        <Text style={{ color: colors.textSecondary, fontSize: 13, marginBottom: 16 }}>
          This screen doesn&apos;t exist.
        </Text>
        <Link href="/" style={{ color: colors.accent, fontSize: 14, fontWeight: "600" }}>
          Go to home
        </Link>
      </View>
    </>
  );
}
