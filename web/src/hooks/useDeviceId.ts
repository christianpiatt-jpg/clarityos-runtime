// hooks/useDeviceId.ts — stable per-browser device id (mesh sync key).

import { useMemo } from "react";

const DEVICE_ID_KEY = "clarityos_device_id";

function getOrCreateDeviceId(): string {
  try {
    const existing = localStorage.getItem(DEVICE_ID_KEY);
    if (existing) return existing;
    const fresh = "web_" + Math.random().toString(36).slice(2, 12);
    localStorage.setItem(DEVICE_ID_KEY, fresh);
    return fresh;
  } catch {
    return "web_ephemeral";
  }
}

export function useDeviceId(): string {
  // useMemo ensures we only touch localStorage once per mount.
  return useMemo(getOrCreateDeviceId, []);
}
