// hooks/useDeviceId.ts (phone) — stable per-install device id.
// Uses AsyncStorage so the id survives app restarts.

import { useEffect, useState } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";

const DEVICE_ID_KEY = "clarityos_device_id";

function freshDeviceId(): string {
  return "phone_" + Math.random().toString(36).slice(2, 12);
}

export function useDeviceId(): string {
  // Synchronous initial value in case AsyncStorage hasn't loaded yet —
  // mesh push falls back to this until the persisted id loads. The persisted
  // value (if any) overwrites once available.
  const [id, setId] = useState<string>(() => freshDeviceId());
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const stored = await AsyncStorage.getItem(DEVICE_ID_KEY);
        if (cancelled) return;
        if (stored) {
          setId(stored);
        } else {
          const fresh = freshDeviceId();
          await AsyncStorage.setItem(DEVICE_ID_KEY, fresh);
          if (!cancelled) setId(fresh);
        }
      } catch { /* best-effort */ }
    })();
    return () => { cancelled = true; };
  }, []);
  return id;
}
