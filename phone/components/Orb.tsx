import React, { useEffect, useRef } from "react";
import { Animated, Easing, View } from "react-native";
import Svg, { Defs, RadialGradient, Stop, Circle } from "react-native-svg";
import { colors } from "../lib/theme";

type Props = { size?: number };

export default function Orb({ size = 200 }: Props) {
  const drift = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(drift, { toValue: 1, duration: 4000, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        Animated.timing(drift, { toValue: 0, duration: 4000, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      ])
    ).start();
  }, [drift]);

  const translateY = drift.interpolate({ inputRange: [0, 1], outputRange: [0, -8] });
  const scale = drift.interpolate({ inputRange: [0, 1], outputRange: [1, 1.04] });

  return (
    <View style={{ width: size + 40, height: size + 40, alignItems: "center", justifyContent: "center" }}>
      <Animated.View style={{ transform: [{ translateY }, { scale }] }}>
        <Svg width={size} height={size} viewBox="0 0 100 100">
          <Defs>
            <RadialGradient id="orb" cx="35%" cy="32%" r="80%">
              <Stop offset="0%" stopColor="#ffffff" />
              <Stop offset="22%" stopColor={colors.accent} />
              <Stop offset="55%" stopColor={colors.accentDeep} />
              <Stop offset="100%" stopColor={colors.accentViolet} />
            </RadialGradient>
            <RadialGradient id="halo" cx="50%" cy="50%" r="50%">
              <Stop offset="0%" stopColor={colors.accent} stopOpacity="0.3" />
              <Stop offset="100%" stopColor={colors.accent} stopOpacity="0" />
            </RadialGradient>
          </Defs>
          <Circle cx="50" cy="50" r="50" fill="url(#halo)" />
          <Circle cx="50" cy="50" r="40" fill="url(#orb)" />
        </Svg>
      </Animated.View>
    </View>
  );
}
