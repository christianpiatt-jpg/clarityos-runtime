import { useRef, useState } from "react";
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
import { router, Stack } from "expo-router";
import ModelSelector, { Model } from "../components/ModelSelector";
import { colors, geometry, spacing, typography } from "../lib/designSystem";
import { routeModelRequest, type ModelId } from "../lib/modelRouter";
import { runLangbridg, type ClarityObject } from "../lib/langbridg";
import { transform } from "../lib/clarity";
import { clearInterrupted, markInterrupted } from "../lib/continuity";
import { setPendingClarity } from "../lib/runtimeBuffer";

const DEFAULT_MODEL: Model = "Copilot";
type Interpreter = "Galileo" | "Tizzy" | "Markov";

type Role = "user" | "engine" | "error";

type Message = {
  id: string;
  role: Role;
  engine: Model;
  interpreter: Interpreter;
  text: string;
  // Engine messages keep their full ClarityObject so the operator can drill
  // into structure/decisions/contradictions later if needed without re-running
  // the pipeline.
  clarity?: ClarityObject;
};

function toModelId(m: Model): ModelId {
  return m.toLowerCase() as ModelId;
}

export default function ChatScreen() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [activeModel, setActiveModel] = useState<Model>(DEFAULT_MODEL);
  const [showSelector, setShowSelector] = useState(false);
  const [focused, setFocused] = useState(false);
  const [busy, setBusy] = useState(false);
  const interpreter: Interpreter = "Galileo"; // provided by runtime
  const scrollRef = useRef<ScrollView>(null);

  function scrollToEnd(animated = true) {
    requestAnimationFrame(() =>
      scrollRef.current?.scrollToEnd({ animated })
    );
  }

  function appendMessage(msg: Message) {
    setMessages((m) => [...m, msg]);
  }

  /**
   * Submit flow:
   *   1. Append user message immediately so the operator sees their input land.
   *   2. Run modelRouter (stub today; real APIs when keys ship via the
   *      cloud proxy) → langbridg → clarity transform.
   *   3. Append the distilled output as an `engine` message inline. No
   *      external navigation — the chat surface IS the surface.
   *   4. On error, append an `error` message in red. The chat stays usable.
   *
   * The full ClarityObject is parked on each engine message + on the runtime
   * buffer (latest only) so /copy / vault save can use it later if wired.
   */
  async function submit() {
    const text = input.trim();
    if (!text || busy) return;
    const id = String(Date.now());
    const engineUsed = activeModel;
    appendMessage({ id, role: "user", engine: engineUsed, interpreter, text });
    setInput("");
    setBusy(true);
    setActiveModel(DEFAULT_MODEL); // revert to default for the next request

    await markInterrupted(id);

    try {
      const r = await routeModelRequest(toModelId(engineUsed), text);
      if (!r.ok) throw new Error(`${r.code}: ${r.error}`);
      const clarity = await runLangbridg(r.raw);
      const distilled = transform(clarity).text;

      // Park the most recent clarity for any /copy-style consumer; the
      // engine message also carries it so older messages remain inspectable.
      setPendingClarity(clarity);

      appendMessage({
        id: id + "_eng",
        role: "engine",
        engine: engineUsed,
        interpreter,
        text: distilled,
        clarity,
      });
      await clearInterrupted();
    } catch (e: any) {
      appendMessage({
        id: id + "_err",
        role: "error",
        engine: engineUsed,
        interpreter,
        text: `pipeline error: ${e?.message || e}`,
      });
    } finally {
      setBusy(false);
    }
  }

  function pickModel(m: Model) {
    setActiveModel(m);
    setShowSelector(false);
  }

  const submitDisabled = busy || !input.trim();

  return (
    <>
      <Stack.Screen
        options={{
          headerRight: () => (
            <Pressable
              onPress={() => router.push("/ingest")}
              hitSlop={8}
              style={({ pressed }) => ({
                opacity: pressed ? 0.6 : 1,
                paddingHorizontal: 8,
              })}
            >
              <Text style={[typography.label12, { color: colors.cyan }]}>INGEST</Text>
            </Pressable>
          ),
        }}
      />
      <SafeAreaView edges={["bottom"]} style={styles.root}>
        <KeyboardAvoidingView
          style={styles.kav}
          behavior={Platform.OS === "ios" ? "padding" : "height"}
        >
          <View style={styles.statusBar}>
            <Pressable onPress={() => !busy && setShowSelector(true)} hitSlop={6}>
              <Text style={[typography.label12, { color: colors.cyan }]}>
                ENGINE: {activeModel.toUpperCase()}
              </Text>
            </Pressable>
            <Text style={[typography.label12, { color: colors.cyan }]}>
              INTERPRETER: {interpreter.toUpperCase()}
            </Text>
          </View>

          <ScrollView
            ref={scrollRef}
            style={styles.list}
            contentContainerStyle={styles.listContent}
            keyboardShouldPersistTaps="handled"
            keyboardDismissMode={Platform.OS === "ios" ? "interactive" : "on-drag"}
            onContentSizeChange={() => scrollToEnd(false)}
          >
            {messages.length === 0 ? (
              <Text style={styles.placeholder}>
                Submit a prompt. Engine response appears below.
              </Text>
            ) : (
              messages.map((msg) => <MessageBlock key={msg.id} msg={msg} />)
            )}

            {busy && (
              <View style={styles.busyBlock}>
                <Text style={[typography.label12, { color: colors.cyan }]}>
                  RUNNING PIPELINE…
                </Text>
                <Text style={[typography.label14, { color: colors.darkGrey, marginTop: 4 }]}>
                  router → langbridg → clarity
                </Text>
              </View>
            )}
          </ScrollView>

          <View style={styles.inputBar}>
            <TextInput
              style={[
                styles.input,
                {
                  borderColor: focused ? colors.cyan : colors.neutralGrey,
                  opacity: busy ? 0.5 : 1,
                },
              ]}
              value={input}
              onChangeText={setInput}
              onFocus={() => {
                setFocused(true);
                scrollToEnd();
              }}
              onBlur={() => setFocused(false)}
              placeholder="Submit input"
              placeholderTextColor={colors.darkGrey}
              onSubmitEditing={submit}
              returnKeyType="send"
              editable={!busy}
              blurOnSubmit={false}
            />
            <Pressable
              onPress={submit}
              disabled={submitDisabled}
              style={({ pressed }) => [
                styles.submit,
                {
                  backgroundColor: pressed && !submitDisabled ? colors.cyan : "transparent",
                  opacity: submitDisabled ? 0.5 : 1,
                },
              ]}
            >
              {({ pressed }) => (
                <Text
                  style={[
                    typography.label14,
                    { color: pressed && !submitDisabled ? colors.black : colors.cyan },
                  ]}
                >
                  {busy ? "…" : "SUBMIT"}
                </Text>
              )}
            </Pressable>
          </View>
        </KeyboardAvoidingView>

        <ModelSelector
          visible={showSelector}
          active={activeModel}
          onSelect={pickModel}
          onClose={() => setShowSelector(false)}
        />
      </SafeAreaView>
    </>
  );
}

// ---------- Message block ----------
function MessageBlock({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  const isEngine = msg.role === "engine";
  const isError = msg.role === "error";

  const labelColor = isError ? colors.red : colors.cyan;
  const bodyColor = isError ? colors.red : colors.white;

  let label: string;
  if (isError) label = "ERROR";
  else if (isUser) label = `USER  ·  ${msg.engine.toUpperCase()}  ·  ${msg.interpreter.toUpperCase()}`;
  else label = `RESPONSE  ·  ${msg.engine.toUpperCase()}  ·  ${msg.interpreter.toUpperCase()}`;

  return (
    <View
      style={[
        styles.messageBlock,
        isEngine && styles.messageBlockEngine,
        isError && styles.messageBlockError,
      ]}
    >
      <Text style={[typography.label12, { color: labelColor, marginBottom: 6 }]}>
        {label}
      </Text>
      <Text style={[typography.body16, { color: bodyColor }]}>{msg.text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.black },
  kav: { flex: 1 },
  statusBar: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.frame,
    paddingVertical: spacing.blockPadding,
    borderBottomWidth: 1,
    borderBottomColor: colors.neutralGrey,
    backgroundColor: colors.black,
  },
  list: { flex: 1 },
  listContent: {
    padding: spacing.frame,
    paddingBottom: spacing.frame,
    flexGrow: 1,
  },
  placeholder: {
    color: colors.darkGrey,
    fontSize: 14,
    paddingVertical: spacing.blockPadding,
  },
  messageBlock: {
    backgroundColor: colors.deepGrey,
    padding: spacing.blockPadding,
    marginBottom: spacing.blockGap,
    borderRadius: geometry.radius0,
    borderWidth: 1,
    borderColor: colors.neutralGrey,
    width: "100%",
  },
  messageBlockEngine: {
    borderColor: colors.cyan,
  },
  messageBlockError: {
    borderColor: colors.red,
  },
  busyBlock: {
    backgroundColor: colors.deepGrey,
    padding: spacing.blockPadding,
    borderWidth: 1,
    borderColor: colors.neutralGrey,
    borderRadius: geometry.radius0,
    marginBottom: spacing.blockGap,
  },
  inputBar: {
    flexDirection: "row",
    alignItems: "center",
    padding: spacing.frame,
    paddingTop: spacing.blockPadding,
    backgroundColor: colors.black,
    borderTopWidth: 1,
    borderTopColor: colors.neutralGrey,
    gap: spacing.gridGap,
  },
  input: {
    flex: 1,
    backgroundColor: colors.deepGrey,
    borderWidth: 1,
    paddingHorizontal: spacing.blockPadding,
    paddingVertical: spacing.blockPadding,
    color: colors.white,
    fontSize: 16,
    borderRadius: geometry.radius0,
  },
  submit: {
    paddingVertical: spacing.buttonPaddingVertical,
    paddingHorizontal: spacing.frame,
    borderWidth: 1,
    borderColor: colors.cyan,
    borderRadius: geometry.radius0,
    alignItems: "center",
    justifyContent: "center",
  },
});
