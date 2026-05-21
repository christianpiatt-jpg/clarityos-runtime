import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { colors, geometry, spacing, typography } from "../lib/designSystem";

export type Model = "Copilot" | "Claude" | "ChatGPT" | "Gemini" | "Local";

type ModelEntry = { name: Model; shape: "square" | "triangle" };

const MODELS: ModelEntry[] = [
  { name: "Copilot", shape: "square" },
  { name: "Claude", shape: "triangle" },
  { name: "ChatGPT", shape: "square" },
  { name: "Gemini", shape: "triangle" },
  { name: "Local", shape: "square" },
];

type Props = {
  visible: boolean;
  active: Model;
  onSelect: (m: Model) => void;
  onClose: () => void;
};

function Icon({ shape, color }: { shape: "square" | "triangle"; color: string }) {
  if (shape === "square") {
    return <View style={{ width: 14, height: 14, backgroundColor: color }} />;
  }
  return (
    <View
      style={{
        width: 0,
        height: 0,
        borderLeftWidth: 7,
        borderRightWidth: 7,
        borderBottomWidth: 13,
        borderLeftColor: "transparent",
        borderRightColor: "transparent",
        borderBottomColor: color,
      }}
    />
  );
}

export default function ModelSelector({ visible, active, onSelect, onClose }: Props) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.container} onPress={() => {}}>
          {MODELS.map((m) => {
            const isActive = m.name === active;
            return (
              <Pressable
                key={m.name}
                onPress={() => onSelect(m.name)}
                style={[
                  styles.item,
                  { borderColor: isActive ? colors.cyan : "transparent" },
                ]}
              >
                <Icon shape={m.shape} color={isActive ? colors.cyan : colors.lightGrey} />
                <Text
                  style={[
                    typography.label16,
                    { color: isActive ? colors.cyan : colors.white, marginLeft: spacing.blockPadding },
                  ]}
                >
                  {m.name}
                </Text>
              </Pressable>
            );
          })}
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.8)",
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.frame,
  },
  container: {
    width: "100%",
    maxWidth: 360,
    backgroundColor: colors.deepGrey,
    padding: spacing.blockPadding,
    borderRadius: geometry.radius4,
  },
  item: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.blockPadding,
    paddingHorizontal: spacing.blockPadding,
    borderWidth: 1,
    marginBottom: spacing.gridGap,
    borderRadius: geometry.radius0,
  },
});
